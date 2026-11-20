import { useState, useEffect } from 'react';
import Sidebar from './Sidebar';
import Header from './Header';
import Icon from '../Icon';
import { API_BASE_URL } from '../../services/api';

export default function Layout({ children, role = 'user' }) {
  const [source, setSource] = useState(null);
  const [googleSetupAvailable, setGoogleSetupAvailable] = useState(false);
  useEffect(() => {
    const reload = () => fetch(`${API_BASE_URL}/api/health`).then(r => r.json()).then(d => {
      setSource(d.source);
      setGoogleSetupAvailable(d.google_setup_available);
    }).catch(() => {});
    reload();
    window.addEventListener('source-updated', reload);
    return () => window.removeEventListener('source-updated', reload);
  }, []);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(() => {
    return localStorage.getItem('bs_sidebar_collapsed') === 'true';
  });

  useEffect(() => {
    const handleCollapseChange = () => {
      setIsCollapsed(localStorage.getItem('bs_sidebar_collapsed') === 'true');
    };
    window.addEventListener('sidebar-collapse-change', handleCollapseChange);
    return () => window.removeEventListener('sidebar-collapse-change', handleCollapseChange);
  }, []);

  return (
    <div className="app-layout">
      {/* Dark overlay — only visible on mobile when sidebar is open */}
      <div
        className={`sidebar-overlay${sidebarOpen ? ' active' : ''}`}
        onClick={() => setSidebarOpen(false)}
      />

      <Sidebar
        role={role}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <div className={`main-content${isCollapsed ? ' collapsed' : ''}`}>
        <Header
          role={role}
          onHamburgerClick={() => setSidebarOpen((prev) => !prev)}
        />
        <main className="page-body fade-in">
          {source && (
            <div className="workspace-source" data-mode={source.mode}>
              <Icon name="sheet" size={16} />
              <strong>{source.mode === "sample" ? "Sample rates" : "Google Sheets"}</strong>
              <span>{source.label}</span>
              {googleSetupAvailable && <a className="btn btn-secondary btn-sm" href="/setup">Connect Google Sheets</a>}
              {source.updated_at && <time dateTime={source.updated_at}>{new Date(source.updated_at).toLocaleString()}</time>}
            </div>
          )}
          {children}
        </main>
      </div>
    </div>
  );
}

