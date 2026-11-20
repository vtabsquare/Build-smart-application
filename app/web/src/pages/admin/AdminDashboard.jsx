import { useState, useEffect } from 'react';
import Layout from '../../components/layout/Layout';
import BuildingStudy from '../../components/BuildingStudy';
import Icon from '../../components/Icon';
import { adminAPI, formatINR } from '../../services/api';

/* ── colour maps for stat card accent borders ─────────────────────────── */
const accentMap = {
  teal:  'linear-gradient(90deg,#0f766e,#14b8a6)',
  blue:  'linear-gradient(90deg,#0891b2,#38bdf8)',
  green: 'linear-gradient(90deg,#16a34a,#4ade80)',
  amber: 'linear-gradient(90deg,#d97706,#fbbf24)',
};

/* ── tiny helper: initials avatar ─────────────────────────────────────── */
function InitialsAvatar({ name, gradient }) {
  const initials = name
    .split(' ')
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() || '')
    .join('');
  return (
    <div
      style={{
        width: 36, height: 36, borderRadius: '50%', flexShrink: 0,
        background: gradient || 'linear-gradient(135deg,#0f766e,#0891b2)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: '#fff', fontSize: 12, fontWeight: 700,
        boxShadow: '0 2px 8px rgba(0,0,0,0.18)',
      }}
    >
      {initials || '?'}
    </div>
  );
}

/* ── avatar gradient pool (cycles) ────────────────────────────────────── */
const avatarGrads = [
  'linear-gradient(135deg,#0f766e,#0891b2)',
  'linear-gradient(135deg,#7c3aed,#db2777)',
  'linear-gradient(135deg,#d97706,#dc2626)',
  'linear-gradient(135deg,#059669,#0891b2)',
  'linear-gradient(135deg,#6d28d9,#0f766e)',
];

export default function AdminDashboard() {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => { loadAnalytics(); }, []);

  const loadAnalytics = async () => {
    try {
      setLoading(true);
      // api.js auto-unwraps {data: {...}} so analytics IS the inner object
      const analytics = await adminAPI.getAnalytics();
      setAnalytics(analytics);
    } catch (err) {
      setError(err.message || 'Failed to load analytics.');
    } finally {
      setLoading(false);
    }
  };

  const stats = analytics
    ? [
        { icon: 'users', label: 'Registered Builders', value: analytics.total_builders ?? '—', color: 'teal' },
        { icon: 'estimate', label: 'Total Estimates Generated', value: analytics.total_estimates ?? '—', color: 'blue' },
        { icon: 'pin', label: 'Active Cities', value: analytics.total_cities ?? analytics.active_cities ?? '—', color: 'amber' },
      ]
    : [
        { icon: 'users', label: 'Registered Builders', value: '—', color: 'teal' },
        { icon: 'estimate', label: 'Total Estimates Generated', value: '—', color: 'blue' },
        { icon: 'pin', label: 'Active Cities', value: '—', color: 'amber' },
      ];

  const recentActivity = analytics?.recent_estimates || [];
  const cityStats = analytics?.city_stats || [];

  return (
    <Layout role="admin">

      <section className="studio-hero studio-hero-admin">
        <div className="studio-hero-content">
          <h1>Administration overview</h1>
          <p>Monitor builder accounts, estimate activity, and coverage by city.</p>
          <div className="studio-hero-actions">
            <button className="btn studio-hero-secondary" onClick={loadAnalytics} disabled={loading}><Icon name="refresh" /> {loading ? 'Refreshing…' : 'Refresh overview'}</button>
          </div>
        </div>
        <BuildingStudy />
      </section>
      {error && (
        <div className="alert alert-red mb-16">
          <span className="alert-icon">⚠</span>
          <div className="alert-body"><div className="alert-title">{error}</div></div>
        </div>
      )}

      {/* ── Stat Cards ─────────────────────────────────────────────────── */}
      <div className="stat-grid" style={{ marginBottom: '28px' }}>
        {stats.map((s) => (
          <div
            key={s.label}
            style={{
              borderRadius: '14px',
              overflow: 'hidden',
              boxShadow: '0 4px 20px rgba(0,0,0,0.07)',
              position: 'relative',
            }}
          >
            {/* gradient accent bottom border */}
            <div style={{
              position: 'absolute', bottom: 0, left: 0, right: 0, height: '3px',
              background: accentMap[s.color] || accentMap.teal,
              borderRadius: '0 0 14px 14px',
            }} />
            <div
              className="stat-card"
              style={{
                borderRadius: '14px 14px 0 0',
                border: 'none',
                paddingBottom: '22px',
                boxShadow: 'none',
                margin: 0,
              }}
            >
              <div className={`stat-icon ${s.color}`}><Icon name={s.icon} size={23} /></div>
              <div className="stat-content">
                <div className="stat-label">{s.label}</div>
                <div className="stat-value" style={{ fontSize: '22px' }}>
                  {loading ? (
                    <span style={{ fontSize: '14px', color: 'var(--color-gray-400)' }}>Loading…</span>
                  ) : s.value}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* ── 2-col grid: City Stats + Recent Activity ────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '24px', marginBottom: '28px' }}>

        {/* City-wise Volume */}
        <div className="card" style={{ borderRadius: '16px', overflow: 'hidden', boxShadow: '0 4px 24px rgba(0,0,0,0.07)' }}>
          <div
            className="card-header"
            style={{
              borderTop: '3px solid',
              borderImage: 'linear-gradient(90deg,#0f766e,#0891b2) 1',
              paddingTop: '18px',
            }}
          >
            <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                width: 28, height: 28, borderRadius: '8px',
                background: 'linear-gradient(135deg,#0f766e,#0891b2)',
                fontSize: '14px',
              }}>🏙</span>
              City-wise Estimate Volume
            </div>
          </div>
          <div className="p-0">
            <div className="table-wrapper" style={{ border: 'none', borderRadius: '0 0 16px 16px', overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
              {loading ? (
                <div style={{ padding: '32px', textAlign: 'center', color: 'var(--color-gray-400)' }}>
                  <div style={{ fontSize: '24px', marginBottom: '8px' }}>⏳</div>
                  Loading city data…
                </div>
              ) : cityStats.length === 0 ? (
                <div style={{ padding: '32px', textAlign: 'center', color: 'var(--color-gray-400)' }}>
                  <div style={{ fontSize: '24px', marginBottom: '8px' }}>🏙</div>
                  No city data yet.
                </div>
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>City</th>
                      <th style={{ textAlign: 'right' }}>Estimates</th>
                      <th style={{ textAlign: 'right' }}>Total Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cityStats.map((c, i) => (
                      <tr key={c.city}>
                        <td className="td-bold">
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <div style={{
                              width: 6, height: 6, borderRadius: '50%',
                              background: `hsl(${(i * 47) % 360},65%,52%)`,
                              flexShrink: 0,
                            }} />
                            {c.city}
                          </div>
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <span style={{
                            background: 'var(--color-gray-100)',
                            borderRadius: '20px',
                            padding: '2px 10px',
                            fontSize: '12px',
                            fontWeight: 600,
                            color: 'var(--color-gray-700)',
                          }}>
                            {c.estimate_count}
                          </span>
                        </td>
                        <td className="td-mono" style={{ textAlign: 'right', color: 'var(--color-primary)', fontWeight: 700 }}>
                          {formatINR(c.total_value)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>

        {/* Recent Activity */}
        <div className="card" style={{ borderRadius: '16px', overflow: 'hidden', boxShadow: '0 4px 24px rgba(0,0,0,0.07)' }}>
          <div
            className="card-header"
            style={{
              borderTop: '3px solid',
              borderImage: 'linear-gradient(90deg,#7c3aed,#db2777) 1',
              paddingTop: '18px',
            }}
          >
            <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                width: 28, height: 28, borderRadius: '8px',
                background: 'linear-gradient(135deg,#7c3aed,#db2777)',
                fontSize: '14px',
              }}>⚡</span>
              Recent Activity
            </div>
          </div>
          <div className="card-body p-0" style={{ padding: 0 }}>
            {loading ? (
              <div style={{ padding: '32px', textAlign: 'center', color: 'var(--color-gray-400)' }}>
                <div style={{ fontSize: '24px', marginBottom: '8px' }}>⏳</div>
                Loading activity…
              </div>
            ) : recentActivity.length === 0 ? (
              <div style={{ padding: '32px', textAlign: 'center', color: 'var(--color-gray-400)' }}>
                <div style={{ fontSize: '24px', marginBottom: '8px' }}>📭</div>
                No recent activity.
              </div>
            ) : (
              <div style={{ position: 'relative' }}>
                {recentActivity.map((a, i) => {
                  const builderName = a.projects?.profiles?.company_name || 'Unknown Builder';
                  const location = a.projects?.location || '—';
                  const total = formatINR(a.grand_total);
                  const date = (a.generated_at || a.created_at || '').split('T')[0];
                  const isLast = i === recentActivity.length - 1;

                  return (
                    <div
                      key={a.id || i}
                      style={{
                        display: 'flex', gap: '14px', padding: '14px 20px',
                        borderBottom: !isLast ? '1px solid var(--color-gray-100)' : 'none',
                        alignItems: 'flex-start',
                        transition: 'background 0.15s',
                      }}
                    >
                      {/* gradient avatar */}
                      <InitialsAvatar
                        name={builderName}
                        gradient={avatarGrads[i % avatarGrads.length]}
                      />

                      {/* content */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--color-gray-900)', marginBottom: '3px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {builderName}
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--color-gray-500)', display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                          <span>Generated estimate</span>
                          <span style={{ color: 'var(--color-gray-300)' }}>·</span>
                          <span>📍 {location}</span>
                          <span style={{ color: 'var(--color-gray-300)' }}>·</span>
                          <span style={{ color: 'var(--color-primary)', fontWeight: 600 }}>{total}</span>
                        </div>
                      </div>

                      {/* date chip */}
                      <div style={{ flexShrink: 0 }}>
                        <span style={{
                          fontSize: '11px', fontWeight: 600,
                          background: 'var(--color-gray-100)',
                          color: 'var(--color-gray-500)',
                          borderRadius: '20px',
                          padding: '3px 10px',
                          whiteSpace: 'nowrap',
                          letterSpacing: '0.3px',
                        }}>
                          {date || '—'}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>



      {/* ── Keyframe for glowing live dot ──────────────────────────────── */}
      <style>{`
        @keyframes admindash-pulse {
          0%,100% { box-shadow: 0 0 0 3px rgba(74,222,128,0.25),0 0 0 6px rgba(74,222,128,0.10); }
          50%      { box-shadow: 0 0 0 5px rgba(74,222,128,0.35),0 0 0 10px rgba(74,222,128,0.08); }
        }
      `}</style>

    </Layout>
  );
}

