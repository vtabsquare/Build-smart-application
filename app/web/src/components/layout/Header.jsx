import Icon from '../Icon';
import { useNavigate } from '../../router';
import { useState, useEffect } from 'react';
import { clearAuthSession, getCurrentUser, isDemoMode } from '../../services/api';

function useWindowWidth() {
  const [width, setWidth] = useState(window.innerWidth);
  useEffect(() => {
    const handler = () => setWidth(window.innerWidth);
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, []);
  return width;
}

const PAGE_TITLES = {
  '/admin/source': { title: 'Data Source', sub: 'Google Sheets connection and field mapping' },
  '/admin/branding': { title: 'Company Branding', sub: 'Company identity for estimates and PDFs' },
  '/dashboard':     { title: 'Dashboard',       sub: 'Overview of your estimates and projects' },
  '/estimate-result': { title: 'Estimate result', sub: 'Review quantities, pricing, and exports' },
  '/new-estimate':  { title: 'New Estimate',    sub: 'Configure a construction estimate' },
  '/projects':      { title: 'My Projects',     sub: 'All your saved estimates and projects' },
  '/settings':      { title: 'Settings',         sub: 'Manage your account and preferences' },
  '/admin':         { title: 'Admin Dashboard', sub: 'Platform overview and statistics' },
  '/admin/users':   { title: 'User Management', sub: 'Manage builder accounts and access' },
  '/admin/rates':   { title: 'Rate Master',     sub: 'Configure material and labour rates by city' },
  '/admin/settings':{ title: 'System Settings', sub: 'Global system configuration' },
};

export default function Header({ role = 'user', onHamburgerClick }) {
  const navigate = useNavigate();
  const path = window.location.pathname;
  const pageInfo = PAGE_TITLES[path] || { title: 'Buildsmart 360', sub: '' };
  const [user, setUser] = useState(getCurrentUser());
  const [showIframeModal, setShowIframeModal] = useState(false);
  const [copiedCode, setCopiedCode] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);
  const isDemo = isDemoMode() || user?.email === 'vtabpublicuser@gmail.com';
  const canExtractIframe = role === 'admin' && !isDemo;
  const windowWidth = useWindowWidth();
  const isSmall = windowWidth <= 480;
  const isMobile = windowWidth <= 768;

  useEffect(() => {
    const handleStorageChange = () => {
      setUser(getCurrentUser());
    };
    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  const handleLogout = () => {
    clearAuthSession();
    navigate('/login');
  };

  const handleSwitchRole = () => {
    if (role === 'builder') navigate('/admin');
    else navigate('/dashboard');
  };

  return (
    <header className="header">
      {/* Hamburger — visible only on mobile via CSS */}
      <button
        className="hamburger-btn"
        onClick={onHamburgerClick}
        title="Menu"
        aria-label="Toggle navigation"
      >
        <Icon name="menu" />
      </button>

      {/* Page title */}
      <div className="header-breadcrumb">
        <div className="breadcrumb-title">{pageInfo.title}</div>
        {pageInfo.sub && <div className="breadcrumb-sub">{pageInfo.sub}</div>}
      </div>

      {/* Actions */}
      <div className="header-actions">
        {canExtractIframe && (
          <button
            className="btn btn-sm"
            onClick={() => setShowIframeModal(true)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '12px',
              fontWeight: '600',
              padding: '6px 12px',
              borderRadius: '8px',
              background: 'linear-gradient(135deg, rgba(15,118,110,0.12) 0%, rgba(8,145,178,0.12) 100%)',
              border: '1px solid rgba(15,118,110,0.3)',
              color: '#0f766e',
              cursor: 'pointer'
            }}
            title="Extract Embeddable iFrame"
          >
            <Icon name="code" size={14} />
            {!isSmall && <span>Extract iFrame</span>}
          </button>
        )}

        {!isMobile && (
          <span
            style={{
              padding: '6px 14px',
              borderRadius: '20px',
              background: isDemo ? 'rgba(234,88,12,0.1)' : 'rgba(15,118,110,0.08)',
              color: isDemo ? '#ea580c' : '#0f766e',
              fontSize: '12px',
              fontWeight: 700,
              letterSpacing: '0.5px',
              textTransform: 'uppercase',
              border: isDemo ? '1px solid rgba(234,88,12,0.25)' : '1px solid rgba(15,118,110,0.18)',
            }}
          >
            {isDemo ? 'Public Demo' : role === 'admin' ? 'Admin workspace' : 'Builder workspace'}
          </span>
        )}

        {/* User avatar */}
        <div
          style={{
            width: '34px', height: '34px', borderRadius: '50%',
            background: 'linear-gradient(135deg, #0f766e 0%, #0891b2 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '13px', fontWeight: '700', color: 'white',
            cursor: isDemo ? 'default' : 'pointer',
            boxShadow: '0 2px 8px rgba(15,118,110,0.35)',
            flexShrink: 0,
            overflow: 'hidden',
          }}
          title={isDemo ? (user?.company_name || 'VTabdemo') : user?.email}
          onClick={isDemo ? undefined : () => navigate(role === 'admin' ? '/admin/settings' : '/settings')}
        >
          {user?.avatar_url ? (
            <img src={user.avatar_url} alt="Profile" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          ) : (
            ((user?.company_name || user?.email || 'V')[0]).toUpperCase()
          )}
        </div>

        {/* Sign out (Disabled in demo mode) */}
        {!isDemo && (
          <button
            className="btn btn-ghost btn-sm"
            onClick={handleLogout}
            aria-label="Sign out"
            style={{ color: 'var(--color-gray-500)', padding: isSmall ? '6px 8px' : undefined }}
          >
            <Icon name="logout" size={16} />{!isSmall && <span>Sign out</span>}
          </button>
        )}
      </div>

      {/* Extract iFrame Modal */}
      {showIframeModal && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(15, 23, 42, 0.65)', backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 9999, padding: '20px'
        }}>
          <div style={{
            background: 'white', borderRadius: '16px', maxWidth: '640px', width: '100%',
            boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)', overflow: 'hidden'
          }}>
            {/* Header */}
            <div style={{
              padding: '20px 24px', background: 'linear-gradient(135deg, #0f766e 0%, #0f172a 100%)',
              color: 'white', display: 'flex', justifyContent: 'space-between', alignItems: 'center'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  width: '36px', height: '36px', borderRadius: '8px', background: 'rgba(255,255,255,0.15)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                  <Icon name="code" size={20} />
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 700 }}>Extract Demo iFrame</h3>
                  <p style={{ margin: '2px 0 0', fontSize: '12px', color: '#99f6e4' }}>Public embed code for {user?.email || 'vtabpublicuser@gmail.com'}</p>
                </div>
              </div>
              <button
                onClick={() => setShowIframeModal(false)}
                style={{ background: 'transparent', border: 'none', color: '#cbd5e1', cursor: 'pointer', fontSize: '20px', lineHeight: 1 }}
              >
                ✕
              </button>
            </div>

            {/* Content */}
            <div style={{ padding: '24px' }}>
              <p style={{ margin: '0 0 16px', fontSize: '14px', color: '#475569', lineHeight: 1.5 }}>
                Embed this interactive estimator directly onto any external website. Visitors are automatically authenticated as <b>VTabdemo</b> with protected demo sandboxing.
              </p>

              {/* Direct Demo URL */}
              <div style={{ marginBottom: '18px' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#334155', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '6px' }}>
                  Direct Demo URL
                </label>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <input
                    type="text"
                    readOnly
                    value={`${window.location.origin}/demo`}
                    style={{
                      flex: 1, padding: '10px 12px', borderRadius: '8px', border: '1px solid #cbd5e1',
                      background: '#f8fafc', fontSize: '13px', color: '#0f172a', fontFamily: 'monospace'
                    }}
                  />
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(`${window.location.origin}/demo`);
                      setCopiedLink(true);
                      setTimeout(() => setCopiedLink(false), 2000);
                    }}
                    style={{
                      padding: '0 16px', borderRadius: '8px', border: 'none',
                      background: copiedLink ? '#059669' : '#0f766e', color: 'white',
                      fontSize: '13px', fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px'
                    }}
                  >
                    {copiedLink ? '✓ Copied' : 'Copy Link'}
                  </button>
                </div>
              </div>

              {/* Embed Code */}
              <div style={{ marginBottom: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <label style={{ fontSize: '12px', fontWeight: 700, color: '#334155', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                    HTML Embed Code
                  </label>
                  <span style={{ fontSize: '11px', color: '#64748b' }}>Responsive (min-height 850px)</span>
                </div>
                <textarea
                  readOnly
                  rows={4}
                  value={`<iframe src="${window.location.origin}/demo" width="100%" height="850" frameborder="0" style="border: 1px solid #e2e8f0; border-radius: 12px; width: 100%; min-height: 850px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);" allow="clipboard-write" title="BuildSmart 360 Cost Estimator"></iframe>`}
                  style={{
                    width: '100%', boxSizing: 'border-box', padding: '12px', borderRadius: '8px',
                    border: '1px solid #cbd5e1', background: '#0f172a', color: '#38bdf8',
                    fontSize: '12px', fontFamily: 'monospace', lineHeight: 1.5, resize: 'none'
                  }}
                />
              </div>

              {/* Badges / Guarantees */}
              <div style={{
                background: '#f0fdfa', border: '1px solid #ccfbf1', borderRadius: '10px',
                padding: '12px 16px', display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px', marginBottom: '20px'
              }}>
                <div style={{ fontSize: '12px', color: '#0f766e', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span>🔒</span> Auto-login: VTabdemo
                </div>
                <div style={{ fontSize: '12px', color: '#0f766e', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span>🚫</span> Settings & Projects Disabled
                </div>
                <div style={{ fontSize: '12px', color: '#0f766e', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span>📄</span> 1 PDF Download / IP limit
                </div>
                <div style={{ fontSize: '12px', color: '#0f766e', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span>✉️</span> Client emailing blocked
                </div>
              </div>

              {/* Action buttons */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  onClick={() => setShowIframeModal(false)}
                  style={{
                    padding: '10px 18px', borderRadius: '8px', border: '1px solid #cbd5e1',
                    background: 'white', color: '#475569', fontSize: '13px', fontWeight: 600, cursor: 'pointer'
                  }}
                >
                  Close
                </button>
                <button
                  onClick={() => {
                    const snippet = `<iframe src="${window.location.origin}/demo" width="100%" height="850" frameborder="0" style="border: 1px solid #e2e8f0; border-radius: 12px; width: 100%; min-height: 850px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);" allow="clipboard-write" title="BuildSmart 360 Cost Estimator"></iframe>`;
                    navigator.clipboard.writeText(snippet);
                    setCopiedCode(true);
                    setTimeout(() => setCopiedCode(false), 2000);
                  }}
                  style={{
                    padding: '10px 20px', borderRadius: '8px', border: 'none',
                    background: copiedCode ? '#059669' : 'linear-gradient(135deg, #0f766e 0%, #0891b2 100%)',
                    color: 'white', fontSize: '13px', fontWeight: 700, cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: '8px', boxShadow: '0 4px 12px rgba(15,118,110,0.25)'
                  }}
                >
                  {copiedCode ? '✓ Copied Embed Code!' : 'Copy Embed Code'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
