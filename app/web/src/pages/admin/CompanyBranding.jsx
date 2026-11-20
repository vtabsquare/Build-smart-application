import { useEffect, useState } from 'react';
import Layout from '../../components/layout/Layout';
import { brandingAPI } from '../../services/api';

const FIELDS = [
  ['name', 'Company name', 'text', 120], ['email', 'Company email', 'email', 254],
  ['phone', 'Company phone', 'tel', 40], ['tax_id', 'GSTIN or tax ID', 'text', 40],
];

export default function CompanyBranding() {
  const [company, setCompany] = useState(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => { brandingAPI.get().then(setCompany).catch(e => setError(e.message)); }, []);

  function setField(field, value) {
    setCompany(previous => ({ ...previous, [field]: value }));
  }

  function loadLogo(event) {
    const file = event.target.files[0];
    if (!file) return;
    if (!['image/png', 'image/jpeg'].includes(file.type) || file.size > 1_000_000) {
      setError('Choose a PNG or JPEG logo under 1 MB.');
      event.target.value = '';
      return;
    }
    setError('');
    const reader = new FileReader();
    reader.onload = () => setField('logo', reader.result);
    reader.onerror = () => setError('The logo file could not be read.');
    reader.readAsDataURL(file);
  }

  async function save(event) {
    event.preventDefault();
    setSaving(true);
    setError('');
    setMessage('');
    try {
      setCompany(await brandingAPI.save(company));
      setMessage('Company details saved for new estimates.');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return <Layout role="admin">
    <section className="studio-workflow-head">
      <h1>Company branding</h1>
      <p>Set the company details printed on new estimates and PDFs.</p>
    </section>
    {error && <p className="alert alert-red" role="alert">{error}</p>}
    {message && <p className="alert alert-green" role="status">{message}</p>}
    {company && <form className="card card-body" aria-label="Company branding" onSubmit={save}>
      <fieldset disabled={saving} style={{ border: 0, minWidth: 0 }}>
        <div className="form-row form-row-2">
          {FIELDS.map(([field, label, type, max]) => <label className="form-group" key={field}>
            <span className="form-label">{label}</span>
            <input className="form-control" type={type} required={field === 'name'} maxLength={max}
              value={company[field] || ''} onChange={e => setField(field, e.target.value)} />
          </label>)}
        </div>
        <label className="form-group">
          <span className="form-label">Company address</span>
          <textarea className="form-control" required rows={3} maxLength={350}
            value={company.address || ''} onChange={e => setField('address', e.target.value)} />
        </label>
        <label className="form-group">
          <span className="form-label">Company logo</span>
          <input className="form-control" type="file" accept="image/png,image/jpeg" onChange={loadLogo} />
        </label>
        {company.logo && <div className="form-group">
          <img src={company.logo} alt="Company logo preview" style={{ maxWidth: 120, maxHeight: 90, display: 'block', marginBottom: 8 }} />
          <button type="button" className="btn btn-secondary" onClick={() => setField('logo', '')}>Remove logo</button>
        </div>}
        <button type="submit" className="btn btn-primary">{saving ? 'Saving…' : 'Save company details'}</button>
      </fieldset>
    </form>}
  </Layout>;
}
