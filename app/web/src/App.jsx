import { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useLocation } from './router';
import { isDemoMode, initDemoSession } from './services/api';
import Login from './pages/auth/Login';
import Dashboard from './pages/user/Dashboard';
import NewProject from './pages/user/NewProject';
import EstimateResult from './pages/user/EstimateResult';
import ProjectHistory from './pages/user/ProjectHistory';
import Settings from './pages/user/Settings';
import AdminDashboard from './pages/admin/AdminDashboard';
import RateMaster from './pages/admin/RateMaster';
import UserManagement from './pages/admin/UserManagement';
import SystemSettings from './pages/admin/SystemSettings';
import DataSource from './pages/admin/DataSource';
import CompanyBranding from './pages/admin/CompanyBranding';

function DemoLanding() {
  const navigate = useNavigate();
  const [error, setError] = useState('');

  useEffect(() => {
    initDemoSession()
      .then(() => {
        navigate('/dashboard', { replace: true });
      })
      .catch((err) => {
        setError(err.message || 'Failed to start demo session');
      });
  }, [navigate]);

  if (error) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#0f172a', color: 'white', padding: '20px', textAlign: 'center' }}>
        <div>
          <div style={{ fontSize: '32px', marginBottom: '12px' }}>⚠️</div>
          <h2 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '8px' }}>Demo Initialization Error</h2>
          <p style={{ color: '#94a3b8', fontSize: '14px', maxWidth: '400px', marginBottom: '20px' }}>{error}</p>
          <button onClick={() => window.location.reload()} style={{ padding: '8px 16px', background: '#0f766e', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer' }}>
            Retry Demo
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#0f172a', color: 'white' }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ width: '48px', height: '48px', border: '4px solid rgba(20,184,166,0.2)', borderTopColor: '#14b8a6', borderRadius: '50%', animation: 'spin 1s linear infinite', margin: '0 auto 16px' }} />
        <p style={{ fontSize: '15px', color: '#94a3b8', fontWeight: 500 }}>Launching BuildSmart Demo Workspace…</p>
        <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
      </div>
    </div>
  );
}

function ProtectedRoute({ children, requiredRole }) {
  const location = useLocation();
  const user = JSON.parse(localStorage.getItem('bs_user') || 'null');
  const demo = isDemoMode();

  if (!user && !demo) return <Navigate to="/login" replace />;

  if (demo) {
    // Disallow Settings and My Projects in demo mode
    if (location.pathname === '/settings' || location.pathname === '/projects') {
      return <Navigate to="/dashboard" replace />;
    }
  }

  if (requiredRole && user?.role !== requiredRole) {
    return <Navigate to={user?.role === 'admin' ? '/admin' : '/dashboard'} replace />;
  }
  return children;
}

function AppContent() {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    // If navigating to /login, clear any demo session flags so login works normally
    if (location.pathname === '/login') {
      sessionStorage.removeItem('bs_is_demo');
      localStorage.removeItem('bs_token');
      localStorage.removeItem('bs_user');
      sessionStorage.removeItem('bs_estimate');
      localStorage.removeItem('bs_active_estimate');
      localStorage.removeItem('bs_new_estimate_draft');
      return;
    }

    // Whenever refreshed in demo / iframe mode, reset the estimate flow to start fresh from dashboard
    const user = JSON.parse(localStorage.getItem('bs_user') || 'null');
    const isDemo = isDemoMode() || user?.email === 'vtabpublicuser@gmail.com';

    if (isDemo) {
      sessionStorage.removeItem('bs_estimate');
      localStorage.removeItem('bs_active_estimate');
      localStorage.removeItem('bs_new_estimate_draft');

      if (location.pathname !== '/dashboard' && location.pathname !== '/demo' && location.pathname !== '/login') {
        navigate('/dashboard', { replace: true });
      }
    }
  }, []);

  return (
    <Routes>
      <Route path="/demo" element={<DemoLanding />} />
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Navigate to={isDemoMode() ? "/dashboard" : "/login"} replace />} />

      {/* Builder Routes - role: 'builder' */}
      <Route path="/dashboard" element={<ProtectedRoute requiredRole="builder"><Dashboard /></ProtectedRoute>} />
      <Route path="/new-estimate" element={<ProtectedRoute requiredRole="builder"><NewProject /></ProtectedRoute>} />
      <Route path="/estimate-result" element={<ProtectedRoute requiredRole="builder"><EstimateResult /></ProtectedRoute>} />
      <Route path="/projects" element={<ProtectedRoute requiredRole="builder"><ProjectHistory /></ProtectedRoute>} />
      <Route path="/settings" element={<ProtectedRoute requiredRole="builder"><Settings /></ProtectedRoute>} />

      {/* Admin Routes - role: 'admin' */}
      <Route path="/admin" element={<ProtectedRoute requiredRole="admin"><AdminDashboard /></ProtectedRoute>} />
      <Route path="/admin/rates" element={<ProtectedRoute requiredRole="admin"><RateMaster /></ProtectedRoute>} />
      <Route path="/admin/users" element={<ProtectedRoute requiredRole="admin"><UserManagement /></ProtectedRoute>} />
      <Route path="/admin/settings" element={<ProtectedRoute requiredRole="admin"><SystemSettings /></ProtectedRoute>} />
      <Route path="/admin/source" element={<ProtectedRoute requiredRole="admin"><DataSource /></ProtectedRoute>} />
      <Route path="/admin/branding" element={<ProtectedRoute requiredRole="admin"><CompanyBranding /></ProtectedRoute>} />

      {/* Catch-all */}
      <Route path="*" element={<Navigate to={isDemoMode() ? "/dashboard" : "/login"} replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}

