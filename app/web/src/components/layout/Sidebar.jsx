import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from '../../router';
import { getCurrentUser } from '../../services/api';
import Icon from '../Icon';

const USER_NAV = [
  {
    section: 'Main',
    items: [
      { label: 'Dashboard', path: '/dashboard' },
      { label: 'New Estimate', path: '/new-estimate' },
      { label: 'My Projects', path: '/projects' },
    ],
  },
  {
    section: 'Account',
    items: [
      { label: 'Settings', path: '/settings' },
    ],
  },
];

const ADMIN_NAV = [
  {
    section: 'Overview',
    items: [
      { label: 'Dashboard', path: '/admin' },
      { label: 'Users', path: '/admin/users' },
    ],
  },
  {
    section: 'Configuration',
    items: [
      { label: 'Google Sheets Source', path: '/admin/source' },
      { label: 'Company Branding', path: '/admin/branding' },
      { label: 'Rate Master', path: '/admin/rates' },
      { label: 'Package & Add-on Rates', path: '/admin/settings' },
    ],
  },
];

export default function Sidebar({ role = 'builder', isOpen = false, onClose }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [user, setUser] = useState(getCurrentUser());
  const [isCollapsed, setIsCollapsed] = useState(() => {
    return localStorage.getItem('bs_sidebar_collapsed') === 'true';
  });

  useEffect(() => {
    const handleStorageChange = () => {
      setUser(getCurrentUser());
    };
    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  useEffect(() => {
    const handleCollapseChange = () => {
      setIsCollapsed(localStorage.getItem('bs_sidebar_collapsed') === 'true');
    };
    window.addEventListener('sidebar-collapse-change', handleCollapseChange);
    return () => window.removeEventListener('sidebar-collapse-change', handleCollapseChange);
  }, []);

  const toggleCollapse = (e) => {
    e.stopPropagation(); // prevent navigation
    const nextVal = !isCollapsed;
    setIsCollapsed(nextVal);
    localStorage.setItem('bs_sidebar_collapsed', String(nextVal));
    window.dispatchEvent(new Event('sidebar-collapse-change'));
  };

  // Close sidebar on route change (mobile)
  useEffect(() => {
    if (onClose) onClose();
  }, [location.pathname]); // eslint-disable-line react-hooks/exhaustive-deps

  const navGroups = role === 'admin' ? ADMIN_NAV : USER_NAV;
  const displayName = user?.company_name || user?.email || (role === 'admin' ? 'Admin User' : 'Builder Account');
  const displayRole = role === 'admin' ? 'Administrator' : 'Builder';

  return (
    <aside className={`sidebar slide-in${isOpen ? ' open' : ''}${isCollapsed ? ' collapsed' : ''}`}>
      {/* Logo */}
      <div className="sidebar-logo">
        <div className="sidebar-logo-mark">
          <div className="logo-icon"><Icon name="building" size={23} /></div>
          <div className="logo-text">
            <span className="logo-name">BuildSmart</span>
            <span className="logo-sub" style={{ letterSpacing: '2.5px', fontWeight: '800', color: 'var(--color-primary-light)' }}>360</span>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        {navGroups.map((group) => (
          <div key={group.section}>
            <div className="nav-section-label">{group.section}</div>
            {group.items.map((item) => {
              const isActive = location.pathname === item.path;
              return (
                <button
                  key={item.path}
                  aria-current={isActive ? "page" : undefined}
                  title={item.label}
                  className={`nav-item ${isActive ? 'active' : ''}`}
                  onClick={() => navigate(item.path)}
                >
                  <span className="nav-item-icon"><Icon route={item.path} /></span>
                  <span>{item.label}</span>
                  {item.badge && <span className="nav-badge">{item.badge}</span>}
                </button>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Footer user profile */}
      <div className="sidebar-footer">
        <div
          className="sidebar-user"
          onClick={() => navigate(role === 'admin' ? '/admin/settings' : '/settings')}
          style={{ cursor: 'pointer' }}
          title="Account settings"
        >
          <div className="user-avatar" style={{ overflow: 'hidden' }}>
            {user?.avatar_url ? (
              <img src={user.avatar_url} alt="Avatar" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            ) : (
              (displayName[0] || '?').toUpperCase()
            )}
          </div>
          <div className="user-info">
            <div className="user-name">{displayName}</div>
            <div className="user-role">{displayRole}</div>
          </div>
          <button type="button" className="studio-sidebar-toggle" onClick={toggleCollapse}
            aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}>
            <Icon name={isCollapsed ? "right" : "left"} size={16} />
          </button>
        </div>
      </div>
    </aside>
  );
}

