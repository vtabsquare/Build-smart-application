// ============================================================
// BuildSmart AI Estimator — API Service Layer
// All API calls route through this file to Flask backend
// ============================================================

export const API_BASE_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');
const BASE_URL = API_BASE_URL;

// ── Demo & Token helpers ────────────────────────────────────────────
export function isInIframe() {
  if (typeof window === 'undefined') return false;
  try {
    return window.self !== window.top;
  } catch {
    return true; // Cross-origin iframe throws on window.top
  }
}

export function isDemoMode() {
  if (typeof window === 'undefined') return false;

  // Inside ANY iframe, it is always the isolated public demo flow
  if (isInIframe()) return true;

  const isDemoPath = window.location.pathname.startsWith('/demo');
  const params = new URLSearchParams(window.location.search);
  const isDemoParam = params.get('demo') === 'true' || params.get('embed') === 'true' || params.get('iframe') === 'true';

  if (isDemoPath || isDemoParam) {
    sessionStorage.setItem('bs_is_demo', 'true');
    return true;
  }

  // Top-level window without demo params:
  // If user is a real logged-in account (e.g. vitabsquare@gmail.com or vigneshrajas.vtab@gmail.com), clear demo flag
  try {
    const realUser = JSON.parse(localStorage.getItem('bs_user') || 'null');
    if (realUser && realUser.email !== 'vtabpublicuser@gmail.com') {
      sessionStorage.removeItem('bs_is_demo');
      return false;
    }
  } catch {}

  return sessionStorage.getItem('bs_is_demo') === 'true';
}

export async function initDemoSession() {
  try {
    sessionStorage.setItem('bs_is_demo', 'true');
    sessionStorage.removeItem('bs_estimate');
    localStorage.removeItem('bs_active_estimate');
    localStorage.removeItem('bs_new_estimate_draft');

    const res = await fetch(`${BASE_URL}/api/auth/demo-session`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Demo-Mode': 'true',
      },
      body: JSON.stringify({}),
    });
    const json = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(json.error || 'Failed to initialize demo session');
    }
    const { token, user } = json.data || json;
    if (token && user) {
      saveAuthSession(token, user);
      return user;
    }
    throw new Error('Invalid demo session response');
  } catch (err) {
    console.error('Demo session init error:', err);
    throw err;
  }
}

export async function checkDemoDownloadStatus() {
  try {
    const res = await fetch(`${BASE_URL}/api/estimates/demo-download-status`, {
      method: 'GET',
      headers: { 'X-Demo-Mode': 'true' },
    });
    const json = await res.json().catch(() => ({}));
    return json.already_downloaded === true;
  } catch {
    return false;
  }
}

export function getToken() {
  if (isDemoMode()) {
    return (
      sessionStorage.getItem('bs_demo_token') ||
      sessionStorage.getItem('bs_token') ||
      localStorage.getItem('bs_demo_token')
    );
  }
  return localStorage.getItem('bs_token');
}

export function getAuthHeaders() {
  const token = getToken();
  const demo = isDemoMode();
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(demo ? { 'X-Demo-Mode': 'true' } : {}),
  };
}

// ── Base request wrapper ─────────────────────────────────────
async function request(method, path, body = null) {
  const options = {
    method,
    headers: getAuthHeaders(),
  };
  if (body !== null) {
    options.body = JSON.stringify(body);
  }
  const res = await fetch(`${BASE_URL}${path}`, options);
  const json = await res.json().catch(() => ({ error: 'Invalid server response' }));
  if (!res.ok) {
    if (res.status === 401) {
      clearAuthSession();
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    throw new Error(json.error || json.message || `Request failed: ${res.status}`);
  }
  // Auto-unwrap the { success, data } envelope used by Flask routes
  return json.data !== undefined ? json.data : json;
}


// ── Auth API ─────────────────────────────────────────────────
export const brandingAPI = {
  get: () => request('GET', '/api/admin/branding'),
  save: (company) => request('PUT', '/api/admin/branding', company),
};

export const authAPI = {
  login: (email, password) =>
    request('POST', '/api/auth/login', { email, password }),

  register: (payload) =>
    request('POST', '/api/auth/register', payload),

  me: () => request('GET', '/api/auth/me'),

  forgotPassword: (email) =>
    request('POST', '/api/auth/forgot-password', { email }),

  verifyOtp: (email, otp) =>
    request('POST', '/api/auth/verify-otp', { email, otp }),

  resetPassword: (email, otp, password) =>
    request('POST', '/api/auth/reset-password', { email, otp, password }),

  updateProfile: (payload) =>
    request('PUT', '/api/auth/profile', payload),
};

// ── Projects API ─────────────────────────────────────────────
export const projectsAPI = {
  list: () => request('GET', '/api/projects'),

  get: (id) => request('GET', `/api/projects/${id}`),

  create: (payload) => request('POST', '/api/projects', payload),

  delete: (id) => request('DELETE', `/api/projects/${id}`),

  updateStatus: (id, status) => request('PUT', `/api/projects/${id}/status`, { status }),

  getSettings: () => request('GET', '/api/projects/settings'),
};

// ── Estimates API ────────────────────────────────────────────
export const estimatesAPI = {
  generate: (params) => request('POST', '/api/estimates/generate', params),

  byProject: (projectId) => request('GET', `/api/estimates/project/${projectId}`),

  get: (estimateId) => request('GET', `/api/estimates/${estimateId}`),

  sharePdf: (estimateId) => request('POST', `/api/estimates/${estimateId}/share-pdf`, {}),
  archivePdf: (estimateId) => request('POST', `/api/estimates/${estimateId}/google-archive`, {}),
};

// ── Admin API ────────────────────────────────────────────────
export const adminAPI = {
  // Users
  getUsers: () => request('GET', '/api/admin/users'),
  approveUser: (id) => request('PUT', `/api/admin/users/${id}/approve`),
  blockUser: (id) => request('PUT', `/api/admin/users/${id}/block`),
  createAdmin: (payload) => request('POST', '/api/admin/create-admin', payload),
  changePassword: (id, password) => request('PUT', `/api/admin/users/${id}/change-password`, { password }),
  deleteUser: (id) => request('DELETE', `/api/admin/users/${id}`),


  // Rates
  getRates: (city = '') =>
    request('GET', `/api/admin/rates${city ? `?city=${encodeURIComponent(city)}` : ''}`),
  addRate: (payload) => request('POST', '/api/admin/rates', payload),
  updateRate: (id, payload) => request('PUT', `/api/admin/rates/${id}`, payload),
  deleteRate: (id) => request('DELETE', `/api/admin/rates/${id}`),

  // Settings
  getSettings: () => request('GET', '/api/admin/settings'),
  updateSetting: (key, value) => request('PUT', `/api/admin/settings/${key}`, { value }),
  updateSettings: (payload) => request('PUT', '/api/admin/settings', payload),
  getCityIndexes: () => request('GET', '/api/admin/city-indexes'),
  updateCityIndex: (city, costIndex, state = 'India') => request('PUT', `/api/admin/city-indexes/${encodeURIComponent(city)}`, { cost_index: costIndex, state }),

  // Analytics
  getAnalytics: () => request('GET', '/api/admin/analytics'),
};

export const sourceAPI = {
  get: () => request('GET', '/api/admin/source'),
  test: config => request('POST', '/api/admin/source/test', config),
  save: config => request('PUT', '/api/admin/source', config),
  refresh: () => request('POST', '/api/admin/source/refresh', {}),
  reconnect: () => request('POST', '/api/admin/source/reconnect', {}),
};

// ── Auth state helpers used across pages ─────────────────────
export function saveAuthSession(token, user) {
  if (isDemoMode() || user?.email === 'vtabpublicuser@gmail.com') {
    sessionStorage.setItem('bs_is_demo', 'true');
    sessionStorage.setItem('bs_demo_token', token);
    sessionStorage.setItem('bs_demo_user', JSON.stringify(user));
    localStorage.setItem('bs_demo_token', token);
    localStorage.setItem('bs_demo_user', JSON.stringify(user));
  } else {
    // Normal builder or admin login in top-level window
    sessionStorage.removeItem('bs_is_demo');
    sessionStorage.removeItem('bs_demo_token');
    sessionStorage.removeItem('bs_demo_user');
    localStorage.setItem('bs_token', token);
    localStorage.setItem('bs_user', JSON.stringify(user));
  }
}

export function clearAuthSession() {
  localStorage.removeItem('bs_token');
  localStorage.removeItem('bs_user');
  sessionStorage.removeItem('bs_is_demo');
  sessionStorage.removeItem('bs_demo_token');
  sessionStorage.removeItem('bs_demo_user');
  sessionStorage.removeItem('bs_estimate');
  localStorage.removeItem('bs_active_estimate');
  localStorage.removeItem('bs_new_estimate_draft');
}

export function getCurrentUser() {
  try {
    if (isDemoMode()) {
      const demoUser = JSON.parse(
        sessionStorage.getItem('bs_demo_user') ||
        sessionStorage.getItem('bs_user') ||
        localStorage.getItem('bs_demo_user') ||
        'null'
      );
      if (demoUser && demoUser.email === 'vtabpublicuser@gmail.com') {
        return demoUser;
      }
      return {
        id: 'e31862e8-e6f7-4c3a-9e6c-71d69c7acc95',
        email: 'vtabpublicuser@gmail.com',
        role: 'builder',
        company_name: 'VTabdemo',
        phone: '9876543210',
        city: 'COIMBATORE',
        is_approved: true
      };
    }
    return JSON.parse(localStorage.getItem('bs_user') || 'null');
  } catch {
    return null;
  }
}

export function formatINR(amount) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(amount || 0);
}

