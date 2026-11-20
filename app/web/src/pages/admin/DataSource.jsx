import { useEffect, useState } from 'react';
import Layout from '../../components/layout/Layout';
import { sourceAPI } from '../../services/api';

const labels = { material_master: 'Material catalogue', material_rates: 'City and material rates', system_settings: 'Packages and settings', city_indexes: 'City indexes' };
const inputStyle = { padding: '10px 12px', border: '1px solid #cbd5e1', borderRadius: 8, width: '100%', color: '#0f172a', background: '#fff' };
export default function DataSource() {
  const [config, setConfig] = useState(null);
  const [status, setStatus] = useState(null);
  const [production, setProduction] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState(() => new URLSearchParams(window.location.search).has('reconnected')
    ? 'Google reconnected. Refresh to load the latest rates.' : '');
  useEffect(() => { sourceAPI.get().then(d => { setConfig(d.config); setStatus(d.status); setProduction(d.production); }).catch(e => setError(e.message)); }, []);
  const updateTable = (table, values) => setConfig(p => ({ ...p, tables: { ...p.tables, [table]: { ...p.tables[table], ...values } } }));
  const run = async (action) => {
    setBusy(true); setError(''); setMessage('');
    try {
      if (action === 'reconnect') {
        const { url } = await sourceAPI.reconnect();
        window.location.assign(url);
        return;
      }
      const result = action === 'test' ? await sourceAPI.test(config) : action === 'save' ? await sourceAPI.save(config) : await sourceAPI.refresh();
      if (action !== 'test') {
        const saved = await sourceAPI.get(); setConfig(saved.config); setStatus(saved.status);
        window.dispatchEvent(new Event('source-updated'));
      }
      setMessage(action === 'test' ? `Validated ${Object.values(result.counts).reduce((a,b) => a+b,0)} rows. Activate to use this data.` : 'Source activated for new estimates. Saved estimates retain their original values.');
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  return <Layout role="admin"><div style={{ maxWidth: 1080, margin: '0 auto' }}>
    <div style={{ background: 'linear-gradient(120deg,#0f172a,#0f766e)', borderRadius: 18, padding: 28, color: 'white', marginBottom: 22 }}>
      <h1 style={{ color: 'white', fontSize: 28, marginBottom: 10 }}>Connect Google Sheets</h1>
      <p>Map your tabs and columns, validate the data, then activate it for new estimates.</p>
    </div>
    {error && <div role="alert" style={{ padding: 16, background: '#fef2f2', color: '#b91c1c', borderRadius: 10, marginBottom: 18 }}>{error}</div>}
    {message && <div role="status" style={{ padding: 16, background: '#ecfdf5', color: '#065f46', borderRadius: 10, marginBottom: 18 }}>{message}</div>}
    {config ? <fieldset disabled={busy} style={{ border: 0, padding: 0, minWidth: 0 }}>
      <section className="card" style={{ padding: 24, marginBottom: 20 }}>
        <h2 style={{ marginBottom: 16 }}>Source connection</h2>
        {status?.access === 'oauth' && <button className="btn btn-secondary" style={{ marginBottom: 16 }} onClick={() => run('reconnect')}>Reconnect Google</button>}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(230px,1fr))', gap: 20 }}>
          <label>Data source<select style={inputStyle} value={config.mode} onChange={e => setConfig({ ...config, mode: e.target.value })}>
            {!production && <option value="sample">Bundled sample data</option>}<option value="google_sheets">Google Sheets</option>
          </select></label>
          <label>Google access<select style={inputStyle} value={config.access} onChange={e => setConfig({ ...config, access: e.target.value })}>
            <option value="public">Public test sheet (Viewer access)</option><option value="service_account">Private sheet (service account)</option><option value="oauth">Connected Google account</option>
          </select></label>
        </div>
        <label style={{ display: 'block', marginTop: 18 }}>Spreadsheet URL or ID<input style={inputStyle} value={config.spreadsheet_id} placeholder="https://docs.google.com/spreadsheets/d/.../edit" onChange={e => setConfig({ ...config, spreadsheet_id: e.target.value })} /></label>
        {config.access === 'oauth' ? (
          <p style={{ marginTop: 14 }}><a href={`https://docs.google.com/spreadsheets/d/${encodeURIComponent(status?.spreadsheet_id || config.spreadsheet_id)}/edit`} target="_blank" rel="noreferrer">Open the connected Google Sheet</a>. Edit the rates there, then refresh below.</p>
        ) : <p style={{ marginTop: 14, color: '#475569', lineHeight: 1.6 }}>Import the four CSV templates in sample_data into four tabs, with headers in row 1.
          {config.access === 'public' ? ' For public test data, share as Anyone with the link, Viewer.' : ' Enable Sheets API, share with the service-account email as Viewer, and set GOOGLE_APPLICATION_CREDENTIALS on the server.'}</p>}
        <p style={{ marginTop: 8, color: '#475569' }}>Sheets supplies estimation masters. Accounts and saved projects stay in local SQLite. Imports are read-only: edit the sheet, then refresh here.</p>
      </section>
      {config.mode === 'google_sheets' && Object.entries(config.tables).map(([table,spec]) => <section key={table} className="card" style={{ padding: 24, marginBottom: 18 }}>
        <h2 style={{ marginBottom: 16 }}>{labels[table]}</h2>
        <label>Tab name<input style={inputStyle} value={spec.sheet} onChange={e => updateTable(table, { sheet: e.target.value })} /></label>
        <div style={{ overflowX: 'auto', marginTop: 18 }}><table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr><th style={{ textAlign: 'left', padding: 10 }}>Application field</th><th style={{ textAlign: 'left', padding: 10 }}>Your sheet header</th></tr></thead>
          <tbody>{Object.entries(spec.columns).map(([key,header]) => <tr key={key}>
            <td style={{ padding: 10, borderTop: '1px solid #e2e8f0' }}><code>{key}</code></td>
            <td style={{ padding: 10, borderTop: '1px solid #e2e8f0' }}><input aria-label={`${table} ${key} header`} style={inputStyle} value={header} onChange={e => updateTable(table, { columns: { ...spec.columns, [key]: e.target.value } })} /></td>
          </tr>)}</tbody></table></div>
      </section>)}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 24 }}>
        <button className="btn btn-secondary" onClick={() => run('test')}>{busy ? 'Working…' : 'Test connection and mapping'}</button>
        <button className="btn btn-primary" onClick={() => run('save')}>Validate and activate</button>
        <button className="btn btn-secondary" onClick={() => run('refresh')}>Refresh saved source</button>
      </div>
    </fieldset> : !error && <p>Loading source configuration…</p>}
    {status && <section className="card" style={{ padding: 24 }}>
      <h2 style={{ marginBottom: 12 }}>Active snapshot</h2><p>{status.label}</p>
      <p style={{ marginTop: 8 }}>Last activated: {new Date(status.updated_at).toLocaleString()}</p>
      {status.counts && <p style={{ marginTop: 8 }}>{Object.entries(status.counts).map(([k,v]) => `${labels[k]}: ${v}`).join(' · ')}</p>}
      <p style={{ marginTop: 12, color: '#64748b' }}>Refresh is manual. If refresh fails, the last validated snapshot stays active.</p>
    </section>}
  </div></Layout>;
}
