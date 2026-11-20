import { BrowserRouter, Routes, Route, Navigate } from './router';
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

function ProtectedRoute({ children, requiredRole }) {
  const user = JSON.parse(localStorage.getItem('bs_user') || 'null');
  if (!user) return <Navigate to="/login" replace />;
  if (requiredRole && user.role !== requiredRole) {
    return <Navigate to={user.role === 'admin' ? '/admin' : '/dashboard'} replace />;
  }
  return children;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<Navigate to="/login" replace />} />

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
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

