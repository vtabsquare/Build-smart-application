import { useEffect, useState } from 'react';
import { useNavigate } from '../../router';
import { API_BASE_URL, authAPI, saveAuthSession } from '../../services/api';
import Icon from '../../components/Icon';
import BuildingStudy from '../../components/BuildingStudy';

export default function Login() {
  const navigate = useNavigate();
  const [googleSetupAvailable, setGoogleSetupAvailable] = useState(false);
  useEffect(() => {
    sessionStorage.removeItem('bs_is_demo');
    fetch(`${API_BASE_URL}/api/health`).then(r => r.json())
      .then(data => setGoogleSetupAvailable(data.google_setup_available)).catch(() => {});
  }, []);
  const [mode, setMode] = useState('login'); // 'login' | 'register'
  const [form, setForm] = useState({
    email: '', password: '', company_name: '', phone: '', city: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showRegisterPassword, setShowRegisterPassword] = useState(false);
  const [showPrivacyModal, setShowPrivacyModal] = useState(false);

  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotStep, setForgotStep] = useState(1); // 1: Send OTP, 2: Verify OTP, 3: Reset Password
  const [forgotOtp, setForgotOtp] = useState('');
  const [newForgotPwd, setNewForgotPwd] = useState('');
  const [confirmForgotPwd, setConfirmForgotPwd] = useState('');
  const [resendTimer, setResendTimer] = useState(0);

  const validatePassword = (password) => {
    if (password.length < 12) {
      return 'Password must be at least 12 characters long.';
    }
    if (password.length > 128) {
      return 'Password must not exceed 128 characters.';
    }
    if (!/[a-z]/.test(password)) {
      return 'Password must contain at least one lowercase letter.';
    }
    if (!/[A-Z]/.test(password)) {
      return 'Password must contain at least one uppercase letter.';
    }
    if (!/[0-9]/.test(password)) {
      return 'Password must contain at least one number.';
    }
    if (!/[^a-zA-Z0-9]/.test(password)) {
      return 'Password must contain at least one special character.';
    }
    return null;
  };

  const getPasswordStrength = (pwd) => {
    if (!pwd) return { score: 0, label: '', color: '#4b5563' };
    let score = 0;
    if (pwd.length >= 12) score += 1;
    if (/[a-z]/.test(pwd) && /[A-Z]/.test(pwd)) score += 1;
    if (/[0-9]/.test(pwd)) score += 1;
    if (/[^a-zA-Z0-9]/.test(pwd)) score += 1;
    
    if (score <= 1) return { score, label: 'Weak', color: '#ef4444' };
    if (score <= 3) return { score, label: 'Medium', color: '#eab308' };
    return { score, label: 'Strong', color: '#22c55e' };
  };

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
    setError('');
    setSuccess('');
  };

  const handleSendOtp = async (e) => {
    if (e) e.preventDefault();
    if (!forgotEmail.trim()) {
      setError('Please enter your email address.');
      return;
    }
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      await authAPI.forgotPassword(forgotEmail.trim());
      setSuccess('If this address can receive a reset code, check your inbox and spam folder.');
      setForgotStep(2);
      setResendTimer(60);
      const timer = setInterval(() => {
        setResendTimer((prev) => {
          if (prev <= 1) {
            clearInterval(timer);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    } catch (err) {
      setError(err.message || 'Failed to send OTP. Please verify your email.');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e) => {
    e.preventDefault();
    if (!forgotOtp.trim()) {
      setError('Please enter the 6-digit OTP.');
      return;
    }
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      await authAPI.verifyOtp(forgotEmail.trim(), forgotOtp.trim());
      setSuccess('OTP verified! Please enter your new password.');
      setForgotStep(3);
    } catch (err) {
      setError(err.message || 'Verification failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    if (!newForgotPwd || !confirmForgotPwd) {
      setError('Please fill in all password fields.');
      return;
    }
    const pwdErr = validatePassword(newForgotPwd);
    if (pwdErr) {
      setError(pwdErr);
      return;
    }
    if (newForgotPwd !== confirmForgotPwd) {
      setError('Passwords do not match.');
      return;
    }
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      localStorage.removeItem('bs_token');
      localStorage.removeItem('bs_user');
      await authAPI.resetPassword(forgotEmail.trim(), forgotOtp.trim(), newForgotPwd);
      setSuccess('Password has been reset successfully! You can now log in.');
      setMode('login');
      setNewForgotPwd('');
      setConfirmForgotPwd('');
    } catch (err) {
      setError(err.message || 'Failed to reset password. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!form.email || !form.password) {
      setError('Please enter your email and password.');
      return;
    }
    setLoading(true);
    try {
      const data = await authAPI.login(form.email, form.password);
      if (data.password_expired) {
        setError('Your password has expired (90 days). You must reset it before logging in.');
        setForgotEmail(form.email.trim());
        setForgotStep(1);
        setMode('forgot');
        return;
      }
      saveAuthSession(data.token, data.user);
      if (data.user.role === 'admin') navigate('/admin');
      else navigate('/dashboard');
    } catch (err) {
      setError(err.message || 'Login failed. Check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    if (!form.email || !form.password || !form.company_name || !form.city) {
      setError('Please fill in all required fields (Email, Password, Company Name, City).');
      return;
    }
    
    // Email regex validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(form.email.trim())) {
      setError('Please enter a valid email address.');
      return;
    }

    const pwdErr = validatePassword(form.password);
    if (pwdErr) {
      setError(pwdErr);
      return;
    }

    // Phone regex validation (if entered)
    if (form.phone && form.phone.trim()) {
      const phoneRegex = /^[6-9]\d{9}$/;
      if (!phoneRegex.test(form.phone.trim())) {
        setError('Please enter a valid 10-digit phone number starting with 6-9.');
        return;
      }
    }
    setLoading(true);
    try {
      await authAPI.register({
        email: form.email,
        password: form.password,
        company_name: form.company_name,
        phone: form.phone,
        city: form.city,
      });
      setSuccess('Registration successful! You can now log in directly.');
      setMode('login');
      setForm({ email: '', password: '', company_name: '', phone: '', city: '' });
    } catch (err) {
      setError(err.message || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="studio-auth">
      <section className="studio-auth-stage" aria-labelledby="studio-auth-heading">
        <div className="studio-brand"><span><Icon name="building" size={25} /></span>BuildSmart <b>360</b></div>
        <div className="studio-auth-intro">
          <h1 id="studio-auth-heading">Construction<br />estimates, <em>from the<br className="desktop-break" /> ground up.</em></h1>
          <p>Plan costs, build an itemized bill of quantities, and export project estimates for your clients.</p>
        </div>
        <BuildingStudy />
      </section>
      <div className="studio-auth-panel">
        <section className="studio-auth-card" aria-label="Account access">
          <div style={styles.cardHeader}>
            <h2 className="studio-auth-title">
              {mode === 'login' ? 'Sign in' : mode === 'forgot' ? 'Reset your password' : 'Create an account'}
            </h2>
            <p className="studio-auth-sub">
              {mode === 'login' ? 'Access your BuildSmart workspace.' : mode === 'forgot' ? 'Recover access to your workspace.' : 'Register as a builder.'}
            </p>
          </div>

          {/* Login Form */}
          {mode === 'login' && (
            <form onSubmit={handleLogin}>
              <div style={styles.formGroup}>
                <label htmlFor="signin-email" style={styles.label}>Email Address</label>
                <input id="signin-email"
                  style={styles.input}
                  type="email"
                  name="email"
                  placeholder="Enter your email address"
                  value={form.email}
                  onChange={handleChange}
                  autoComplete="email"
                />
              </div>
              <div style={styles.formGroup}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <label htmlFor="signin-password" style={styles.label}>Password</label>
                  <button
                    type="button"
                    style={styles.forgotBtn}
                    onClick={() => {
                      setMode('forgot');
                      setForgotEmail(form.email);
                      setForgotStep(1);
                      setForgotOtp('');
                      setNewForgotPwd('');
                      setConfirmForgotPwd('');
                      setError('');
                      setSuccess('');
                    }}
                  >
                    Forgot password?
                  </button>
                </div>
                <div style={{ position: 'relative' }}>
                  <input id="signin-password"
                    style={{ ...styles.input, paddingRight: '42px' }}
                    type={showPassword ? "text" : "password"}
                    name="password"
                    placeholder="Enter your password"
                    value={form.password}
                    onChange={handleChange}
                    autoComplete="current-password"
                  />
                  <button
                    type="button"
                    style={{
                      position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)',
                      background: 'none', border: 'none', color: 'rgba(255,255,255,0.45)',
                      fontSize: '18px', cursor: 'pointer', display: 'flex', alignItems: 'center', padding: 0
                    }}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    <Icon name={showPassword ? "eyeOff" : "eye"} size={18} />
                  </button>
                </div>
              </div>

              {error && <div role="alert" style={styles.errorBox}>{error}</div>}
              {success && <div role="status" style={styles.successBox}>{success}</div>}

              <button
                type="submit"
                style={{ ...styles.submitBtn, opacity: loading ? 0.75 : 1 }}
                disabled={loading}
              >
                {loading ? 'Signing in...' : 'Sign in'}
              </button>

              <div style={styles.switchMode}>
                New builder?{' '}
                <button type="button" style={styles.linkBtn} onClick={() => { setMode('register'); setError(''); setSuccess(''); }}>
                  Register here
                </button>
              </div>
            </form>
          )}

          {/* Register Form */}
          {mode === 'register' && (
            <form onSubmit={handleRegister}>
              <div style={styles.formGroup}>
                <label htmlFor="register-company" style={styles.label}>Company Name *</label>
                <input id="register-company" style={styles.input} type="text" name="company_name" placeholder="ABC Constructions Pvt Ltd" value={form.company_name} onChange={handleChange} />
              </div>
              <div style={styles.formGroup}>
                <label htmlFor="register-email" style={styles.label}>Email Address *</label>
                <input id="register-email" style={styles.input} type="email" name="email" placeholder="builder@company.com" value={form.email} onChange={handleChange} autoComplete="email" />
              </div>              <div style={styles.formGroup}>
                <label htmlFor="register-password" style={styles.label}>Password *</label>
                <div style={{ position: 'relative' }}>
                  <input id="register-password"
                    style={{ ...styles.input, paddingRight: '42px' }}
                    type={showRegisterPassword ? "text" : "password"}
                    name="password"
                    placeholder="At least 12 characters with symbol, number, caps"
                    value={form.password}
                    onChange={handleChange}
                    autoComplete="new-password"
                  />
                  <button
                    type="button"
                    style={{
                      position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)',
                      background: 'none', border: 'none', color: 'rgba(255,255,255,0.45)',
                      fontSize: '18px', cursor: 'pointer', display: 'flex', alignItems: 'center', padding: 0
                    }}
                    aria-label={showRegisterPassword ? "Hide password" : "Show password"}
                    onClick={() => setShowRegisterPassword(!showRegisterPassword)}
                  >
                    <Icon name={showRegisterPassword ? "eyeOff" : "eye"} size={18} />
                  </button>
                </div>
                {form.password && (
                  <div style={{ marginTop: '8px', fontSize: '12px', color: 'rgba(255,255,255,0.7)' }}>
                    Password Strength: <span style={{ color: getPasswordStrength(form.password).color, fontWeight: 'bold' }}>{getPasswordStrength(form.password).label}</span>
                    <div style={{ display: 'flex', gap: '4px', marginTop: '4px', height: '4px' }}>
                      <div style={{ flex: 1, height: '100%', backgroundColor: getPasswordStrength(form.password).score >= 1 ? getPasswordStrength(form.password).color : '#374151', borderRadius: '2px' }}></div>
                      <div style={{ flex: 1, height: '100%', backgroundColor: getPasswordStrength(form.password).score >= 3 ? getPasswordStrength(form.password).color : '#374151', borderRadius: '2px' }}></div>
                      <div style={{ flex: 1, height: '100%', backgroundColor: getPasswordStrength(form.password).score >= 4 ? getPasswordStrength(form.password).color : '#374151', borderRadius: '2px' }}></div>
                    </div>
                  </div>
                )}
              </div>

              <div style={styles.formRow}>
                <div style={{ ...styles.formGroup, flex: 1 }}>
                  <label htmlFor="register-phone" style={styles.label}>Phone</label>
                  <input id="register-phone" style={styles.input} type="tel" name="phone" placeholder="9800000000" value={form.phone} onChange={handleChange} />
                </div>
                <div style={{ ...styles.formGroup, flex: 1 }}>
                  <label htmlFor="register-city" style={styles.label}>City *</label>
                  <input id="register-city" style={styles.input} type="text" name="city" placeholder="Mumbai" value={form.city} onChange={handleChange} />
                </div>
              </div>


              {error && <div role="alert" style={styles.errorBox}>{error}</div>}
              {success && <div role="status" style={styles.successBox}>{success}</div>}

              <button
                type="submit"
                style={{ ...styles.submitBtn, opacity: loading ? 0.75 : 1 }}
                disabled={loading}
              >
                {loading ? 'Registering...' : 'Submit Registration →'}
              </button>

              <div style={styles.switchMode}>
                Already have an account?{' '}
                <button type="button" style={styles.linkBtn} onClick={() => { setMode('login'); setError(''); setSuccess(''); }}>
                  Sign in
                </button>
              </div>
            </form>
          )}

          {/* Forgot Password Flow */}
          {mode === 'forgot' && (
            <div>
              <div style={styles.cardHeader}>
                <div style={styles.cardTitle}>Reset Password</div>
                <div style={styles.cardSub}>
                  {forgotStep === 1 && 'Enter your email to receive a password reset OTP'}
                  {forgotStep === 2 && `Enter the 6-digit OTP sent to ${forgotEmail}`}
                  {forgotStep === 3 && 'Enter and confirm your new password'}
                </div>
              </div>

              {forgotStep === 1 && (
                <form onSubmit={handleSendOtp}>
                  <div style={styles.formGroup}>
                    <label htmlFor="recovery-email" style={styles.label}>Email Address</label>
                    <input id="recovery-email"
                      style={styles.input}
                      type="email"
                      placeholder="builder@company.com"
                      value={forgotEmail}
                      onChange={(e) => { setForgotEmail(e.target.value); setError(''); setSuccess(''); }}
                      required
                    />
                  </div>

                  {error && <div role="alert" style={styles.errorBox}>{error}</div>}
                  {success && <div role="status" style={styles.successBox}>{success}</div>}

                  <button
                    type="submit"
                    style={{ ...styles.submitBtn, opacity: loading ? 0.75 : 1 }}
                    disabled={loading}
                  >
                    {loading ? 'Sending...' : 'Send OTP via Email →'}
                  </button>
                </form>
              )}

              {forgotStep === 2 && (
                <form onSubmit={handleVerifyOtp}>
                  <div style={styles.formGroup}>
                    <label htmlFor="recovery-otp" style={styles.label}>One-Time Password (OTP)</label>
                    <input id="recovery-otp"
                      style={{ ...styles.input, textAlign: 'center', letterSpacing: '4px', fontSize: '18px', fontWeight: 'bold' }}
                      type="text"
                      placeholder="000000"
                      maxLength={6}
                      value={forgotOtp}
                      onChange={(e) => { setForgotOtp(e.target.value.replace(/\D/g, '')); setError(''); setSuccess(''); }}
                      required
                    />
                  </div>

                  {error && <div role="alert" style={styles.errorBox}>{error}</div>}
                  {success && <div role="status" style={styles.successBox}>{success}</div>}

                  <button
                    type="submit"
                    style={{ ...styles.submitBtn, opacity: loading ? 0.75 : 1 }}
                    disabled={loading}
                  >
                    {loading ? 'Verifying...' : 'Verify OTP Code →'}
                  </button>

                  <div style={{ textAlign: 'center', marginTop: '10px' }}>
                    <button
                      type="button"
                      style={{ ...styles.linkBtn, color: resendTimer > 0 ? 'rgba(255,255,255,0.3)' : '#2dd4bf' }}
                      onClick={handleSendOtp}
                      disabled={resendTimer > 0 || loading}
                    >
                      {resendTimer > 0 ? `Resend OTP in ${resendTimer}s` : 'Resend OTP'}
                    </button>
                  </div>
                </form>
              )}

              {forgotStep === 3 && (
                <form onSubmit={handleResetPassword}>
                  <div style={styles.formGroup}>
                    <label htmlFor="recovery-password" style={styles.label}>New Password</label>
                    <input id="recovery-password"
                      style={styles.input}
                      type="password"
                      placeholder="At least 12 characters with symbol, number, caps"
                      value={newForgotPwd}
                      onChange={(e) => { setNewForgotPwd(e.target.value); setError(''); setSuccess(''); }}
                      required
                    />
                    {newForgotPwd && (
                      <div style={{ marginTop: '8px', fontSize: '12px', color: 'rgba(255,255,255,0.7)' }}>
                        Password Strength: <span style={{ color: getPasswordStrength(newForgotPwd).color, fontWeight: 'bold' }}>{getPasswordStrength(newForgotPwd).label}</span>
                        <div style={{ display: 'flex', gap: '4px', marginTop: '4px', height: '4px' }}>
                          <div style={{ flex: 1, height: '100%', backgroundColor: getPasswordStrength(newForgotPwd).score >= 1 ? getPasswordStrength(newForgotPwd).color : '#374151', borderRadius: '2px' }}></div>
                          <div style={{ flex: 1, height: '100%', backgroundColor: getPasswordStrength(newForgotPwd).score >= 3 ? getPasswordStrength(newForgotPwd).color : '#374151', borderRadius: '2px' }}></div>
                          <div style={{ flex: 1, height: '100%', backgroundColor: getPasswordStrength(newForgotPwd).score >= 4 ? getPasswordStrength(newForgotPwd).color : '#374151', borderRadius: '2px' }}></div>
                        </div>
                      </div>
                    )}
                  </div>

                  <div style={styles.formGroup}>
                    <label htmlFor="recovery-confirm" style={styles.label}>Confirm New Password</label>
                    <input id="recovery-confirm"
                      style={styles.input}
                      type="password"
                      placeholder="Re-enter new password"
                      value={confirmForgotPwd}
                      onChange={(e) => { setConfirmForgotPwd(e.target.value); setError(''); setSuccess(''); }}
                      required
                    />
                  </div>

                  {error && <div role="alert" style={styles.errorBox}>{error}</div>}
                  {success && <div role="status" style={styles.successBox}>{success}</div>}

                  <button
                    type="submit"
                    style={{ ...styles.submitBtn, opacity: loading ? 0.75 : 1 }}
                    disabled={loading}
                  >
                    {loading ? 'Resetting...' : 'Reset Password & Log In →'}
                  </button>
                </form>
              )}

              <div style={styles.switchMode}>
                Remembered your password?{' '}
                <button type="button" style={styles.linkBtn} onClick={() => { setMode('login'); setError(''); setSuccess(''); }}>
                  Back to Sign In
                </button>
              </div>
            </div>
          )}
          <div style={styles.footerNote}>
            {googleSetupAvailable && <div><a style={styles.privacyLink} href="/setup">Connect Google Sheets</a></div>}
            <button 
              type="button" 
              style={styles.privacyLink} 
              onClick={() => setShowPrivacyModal(true)}
            >
              Privacy Policy & Terms of Service
            </button>
          </div>
        </section>
      </div>

      {/* Privacy Policy & Terms Modal */}
      {showPrivacyModal && (
        <div style={styles.modalOverlay}>
          <div style={styles.modalContent}>
            <div style={styles.modalHeader}>
              <h3 style={styles.modalTitle}>Privacy Policy & Terms of Service</h3>
              <button 
                type="button" 
                style={styles.modalCloseBtn} 
                onClick={() => setShowPrivacyModal(false)}
              >
                ✕
              </button>
            </div>
            <div style={styles.modalBody}>
              <h4 style={styles.sectionHeader}>1. Introduction</h4>
              <p style={styles.paragraph}>
                Welcome to BuildSmart 360 ("we", "our", or "us"). We are committed to protecting the business and personal data of construction professionals and builders using our platform. This policy explains what information we collect, how we store it, and your rights under Indian data protection regulations (DPDP Act).
              </p>
              
              <h4 style={styles.sectionHeader}>2. Information Collection</h4>
              <p style={styles.paragraph}>
                We collect minimum business profile details necessary for verification and account setup:
                <ul style={{ paddingLeft: '20px', marginTop: '8px' }}>
                  <li>Company Name / Business Entity</li>
                  <li>Registered Business Email & Phone Number</li>
                  <li>City of Operation</li>
                </ul>
                All cost estimate details, material selections, and project layouts are stored under your owner account boundaries. We do not sell or share your business data.
              </p>

              <h4 style={styles.sectionHeader}>3. Data Security & Storage</h4>
              <p style={styles.paragraph}>
                All account databases, estimation items, and files are hosted securely in the cloud utilizing AES-256 block-level Transparent Data Encryption (TDE) at rest. Communication between your browser and our server is secured using SSL/TLS encryption.
              </p>

              <h4 style={styles.sectionHeader}>4. Your Rights (Deletion & Access)</h4>
              <p style={styles.paragraph}>
                You retain complete ownership over your account data. You have the right to request permanent deletion of your profile, projects, and cost estimates. Deleting your account will cascade-purge all linked assets permanently from our cloud databases.
              </p>

              <h4 style={styles.sectionHeader}>5. Terms of Service</h4>
              <p style={styles.paragraph}>
                By registering on BuildSmart 360, you agree to supply authentic business credentials. The estimations calculated by our AI engine are based on localized rates and standard engineering coefficients, and should be verified prior to signing formal commercial construction contracts.
              </p>
            </div>
            <div style={styles.modalFooter}>
              <button 
                type="button" 
                style={styles.modalCloseActionBtn} 
                onClick={() => setShowPrivacyModal(false)}
              >
                I Understand
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

/* ─── Styles ─── */
const styles = {
  cardHeader: { marginBottom: '28px' },
  formGroup: { marginBottom: '14px' },
  formRow: { display: 'flex', gap: '12px' },
  label: { display: 'block', fontSize: '11px', fontWeight: 700, color: 'rgba(255,255,255,0.6)', marginBottom: '7px', letterSpacing: '0.07em', textTransform: 'uppercase' },
  input: {
    width: '100%', padding: '11px 14px', borderRadius: '10px',
    border: '1.5px solid rgba(255,255,255,0.14)',
    fontSize: '13px', color: 'rgba(255,255,255,0.92)', background: 'rgba(255,255,255,0.08)',
    backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)', outline: 'none',
    transition: 'all 0.2s ease', fontFamily: 'inherit', boxSizing: 'border-box', fontWeight: 500,
  },
  errorBox: {
    background: 'rgba(220,38,38,0.20)', border: '1px solid rgba(220,38,38,0.35)', color: '#fca5a5',
    borderRadius: '8px', padding: '10px 14px', fontSize: '12px', marginBottom: '14px',
  },
  successBox: {
    background: 'rgba(5,150,105,0.20)', border: '1px solid rgba(5,150,105,0.35)', color: '#6ee7b7',
    borderRadius: '8px', padding: '10px 14px', fontSize: '12px', marginBottom: '14px',
  },
  submitBtn: {
    width: '100%', padding: '12px',
    background: 'linear-gradient(135deg, #0f766e 0%, #0891b2 100%)',
    color: 'white',
    border: 'none',
    borderRadius: '10px', fontSize: '14px', fontWeight: 700,
    cursor: 'pointer', letterSpacing: '0.02em', fontFamily: 'inherit',
    transition: 'all 0.2s ease', marginBottom: '12px',
    boxShadow: '0 6px 24px rgba(15,118,110,0.50)',
  },
  switchMode: { textAlign: 'center', fontSize: '12px', color: 'rgba(255,255,255,0.45)', marginTop: '4px' },
  linkBtn: {
    background: 'none', border: 'none', color: '#2dd4bf', fontWeight: 600, fontSize: '12px',
    cursor: 'pointer', fontFamily: 'inherit', padding: 0,
  },
  forgotBtn: {
    background: 'none', border: 'none', color: '#2dd4bf', fontWeight: 600, fontSize: '11px',
    cursor: 'pointer', fontFamily: 'inherit', padding: 0, textTransform: 'uppercase', letterSpacing: '0.05em',
  },
  footerNote: { marginTop: '18px', fontSize: '11px', color: 'rgba(255,255,255,0.25)', textAlign: 'center' },
  privacyLink: {
    background: 'none',
    border: 'none',
    color: '#2dd4bf',
    fontSize: '11px',
    cursor: 'pointer',
    textDecoration: 'underline',
    padding: 0,
    marginTop: '4px',
    fontFamily: 'inherit',
  },
  modalOverlay: {
    position: 'fixed',
    inset: 0,
    backgroundColor: 'rgba(4, 9, 20, 0.85)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 9999,
    padding: '20px',
  },
  modalContent: {
    backgroundColor: '#1e293b',
    borderRadius: '16px',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    width: '100%',
    maxWidth: '600px',
    display: 'flex',
    flexDirection: 'column',
    maxHeight: '85vh',
    boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 10px 10px -5px rgba(0, 0, 0, 0.5)',
  },
  modalHeader: {
    padding: '20px 24px',
    borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  modalTitle: {
    color: '#ffffff',
    fontSize: '18px',
    fontWeight: '700',
    margin: 0,
    background: 'linear-gradient(90deg, #2dd4bf, #38bdf8)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
  },
  modalCloseBtn: {
    background: 'none',
    border: 'none',
    color: 'rgba(255,255,255,0.5)',
    fontSize: '18px',
    cursor: 'pointer',
    padding: '4px',
    lineHeight: 1,
  },
  modalBody: {
    padding: '24px',
    overflowY: 'auto',
    color: 'rgba(255, 255, 255, 0.8)',
    fontSize: '14px',
    lineHeight: '1.6',
    textAlign: 'left',
  },
  sectionHeader: {
    color: '#ffffff',
    fontSize: '15px',
    fontWeight: '600',
    marginTop: '20px',
    marginBottom: '8px',
  },
  paragraph: {
    marginBottom: '16px',
    color: 'rgba(255, 255, 255, 0.7)',
  },
  modalFooter: {
    padding: '16px 24px',
    borderTop: '1px solid rgba(255, 255, 255, 0.08)',
    display: 'flex',
    justifyContent: 'flex-end',
  },
  modalCloseActionBtn: {
    backgroundColor: '#0f766e',
    color: '#ffffff',
    border: 'none',
    padding: '8px 20px',
    borderRadius: '8px',
    fontWeight: '600',
    fontSize: '14px',
    cursor: 'pointer',
    transition: 'all 0.2s',
    boxShadow: '0 4px 12px rgba(15,118,110,0.3)',
  }
};

