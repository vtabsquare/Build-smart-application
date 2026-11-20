import { useState, useEffect } from 'react';
import { useNavigate } from '../../router';
import Layout from '../../components/layout/Layout';
import BuildingStudy from '../../components/BuildingStudy';
import Icon from '../../components/Icon';
import { projectsAPI, getCurrentUser, formatINR, clearAuthSession } from '../../services/api';


export default function Dashboard() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const user = getCurrentUser();

  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = async () => {
    try {
      setLoading(true);
      const data = await projectsAPI.list();
      // api.js auto-unwraps {data: [...]} so data IS the array
      setProjects(Array.isArray(data) ? data : []);
    } catch (err) {
      if (err.message?.includes('401') || err.message?.toLowerCase().includes('unauthorized')) {
        clearAuthSession();
        navigate('/login');
      } else {
        setError(err.message || 'Failed to load projects.');
      }
    } finally {
      setLoading(false);
    }
  };

  const recentProjects = projects.slice(0, 5);
  const totalValue = projects.reduce((s, p) => {
    const estimates = p.estimates || [];
    const latest = estimates[0];
    return s + (latest?.grand_total || 0);
  }, 0);



  return (
    <Layout role="builder">

      <section className="studio-hero dashboard-welcome-banner">
        <div className="studio-hero-content">
          <h1>{user?.company_name ? 'Welcome back, ' + user.company_name : 'Your estimation workspace'}</h1>
          <p>Start a construction estimate or pick up a saved project.</p>
          <div className="studio-hero-actions">
            <button className="btn studio-hero-primary" onClick={() => navigate('/new-estimate')}><Icon name="plus" /> New estimate</button>
            <button className="btn studio-hero-secondary" onClick={() => navigate('/projects')}><Icon name="folder" /> My projects</button>
          </div>
        </div>
        <BuildingStudy />
      </section>
      <div className="stat-grid">

        {/* Total Projects */}
        <div
          className="stat-card"
          style={{ borderLeft: '4px solid #0f766e', transition: 'transform 0.2s, box-shadow 0.2s' }}
          onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-3px)'; e.currentTarget.style.boxShadow = '0 10px 28px rgba(15,118,110,0.18)'; }}
          onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = ''; }}
        >
          <div className="stat-icon teal" style={{ background: 'linear-gradient(135deg, #0f766e, #14b8a6)' }}><Icon name="folder" size={23} /></div>
          <div className="stat-content">
            <div className="stat-label">Total Projects</div>
            <div className="stat-value">{loading ? '—' : projects.length}</div>
          </div>
        </div>


        {/* Total Estimate Value */}
        <div
          className="stat-card"
          style={{ borderLeft: '4px solid #0891b2', transition: 'transform 0.2s, box-shadow 0.2s' }}
          onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-3px)'; e.currentTarget.style.boxShadow = '0 10px 28px rgba(8,145,178,0.18)'; }}
          onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = ''; }}
        >
          <div className="stat-icon blue" style={{ background: 'linear-gradient(135deg, #0891b2, #38bdf8)' }}><Icon name="estimate" size={23} /></div>
          <div className="stat-content">
            <div className="stat-label">Total Estimate Value</div>
            <div className="stat-value" style={{ fontSize: '16px' }}>
              {loading ? '—' : formatINR(totalValue)}
            </div>
          </div>
        </div>

      </div>

      {/* ── Error ──────────────────────────────────────────────────── */}
      {error && (
        <div className="alert alert-red mb-16">
          <span className="alert-icon">⚠</span>
          <div className="alert-body"><div className="alert-title">{error}</div></div>
        </div>
      )}

      {/* ── Recent Estimates Card ───────────────────────────────────── */}
      <div className="card" style={{ overflow: 'hidden', marginBottom: '20px' }}>
        <div
          className="card-header"
          style={{
            background: 'linear-gradient(to right, var(--color-gray-50), #ffffff)',
            borderBottom: '1px solid var(--color-gray-100)',
          }}
        >
          <div>
            <div className="card-title">Recent Estimates</div>
            <div className="card-subtitle">Your last {recentProjects.length} projects</div>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={() => navigate('/projects')}>
            View All
          </button>
        </div>

        <div className="p-0">
          <div className="table-wrapper" style={{ border: 'none', borderRadius: '0 0 12px 12px' }}>
            {loading ? (
              <div style={{
                padding: '48px',
                textAlign: 'center',
                color: 'var(--text-muted)',
                fontSize: '15px',
              }}>
                <div style={{ fontSize: '28px', marginBottom: '10px', opacity: 0.5 }}>⏳</div>
                Loading projects…
              </div>

            ) : recentProjects.length === 0 ? (
              /* ── Beautiful Empty State ─────────────────────────── */
              <div style={{
                padding: '64px 32px',
                textAlign: 'center',
                background: 'linear-gradient(180deg, #f0fdfa 0%, #ffffff 100%)',
              }}>
                <div style={{ fontSize: '56px', marginBottom: '16px', lineHeight: 1 }}>📭</div>
                <div style={{
                  fontSize: '22px',
                  fontWeight: 800,
                  background: 'linear-gradient(135deg, #0f766e, #0891b2)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  backgroundClip: 'text',
                  marginBottom: '10px',
                }}>
                  No Estimates Yet
                </div>
                <div style={{
                  fontSize: '14px',
                  color: 'var(--text-muted)',
                  maxWidth: '320px',
                  margin: '0 auto 24px',
                  lineHeight: 1.6,
                }}>
                  Start your first construction estimate and get AI-powered cost breakdowns instantly.
                </div>
                <button
                  className="btn btn-primary"
                  onClick={() => navigate('/new-estimate')}
                  style={{ borderRadius: '50px', padding: '11px 28px', fontWeight: 700 }}
                >
                  ＋ Create Your First Estimate
                </button>
              </div>

            ) : (
              <table>
                <thead>
                  <tr style={{ background: 'linear-gradient(to right, #f0fdfa, #e0f2fe)' }}>
                    <th style={{ color: '#0f766e', fontWeight: 700 }}>Project Name</th>
                    <th style={{ color: '#0f766e', fontWeight: 700 }}>Location</th>
                    <th style={{ color: '#0f766e', fontWeight: 700 }}>Area</th>
                    <th style={{ color: '#0f766e', fontWeight: 700 }}>Type</th>
                    <th style={{ color: '#0f766e', fontWeight: 700 }}>Total Estimate</th>
                    <th style={{ color: '#0f766e', fontWeight: 700 }}>Date</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {recentProjects.map((p) => {
                    const latestEst = (p.estimates || [])[0];
                    const status = latestEst?.status || 'Draft';
                    const date = (p.created_at || '').split('T')[0];
                    return (
                      <tr
                        key={p.id}
                        style={{ transition: 'background 0.15s ease' }}
                        onMouseEnter={e => e.currentTarget.style.background = '#f0fdfa'}
                        onMouseLeave={e => e.currentTarget.style.background = ''}
                      >
                        <td className="td-bold">{p.name}</td>
                        <td className="text-muted">{p.location}</td>
                        <td>{(p.total_sqft || 0).toLocaleString()} sqft</td>
                        <td><span className="badge badge-gray">{p.building_type || '—'}</span></td>
                        <td style={{
                          fontFamily: 'monospace',
                          fontWeight: 700,
                          color: '#0f766e',
                          fontSize: '13px',
                        }}>
                          {latestEst ? formatINR(latestEst.grand_total) : '—'}
                        </td>
                        <td className="text-muted text-sm">{date}</td>
                        <td>
                          <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => navigate('/projects')}
                            style={{ fontWeight: 600, color: '#0f766e' }}
                          >
                            Open →
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>



    </Layout>
  );
}

