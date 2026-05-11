import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { auth } from '../api/client';
import { setToken, setUser } from '../utils/auth';

function LoginPage() {
  // useSearchParams retained from the existing file for forward compatibility
  // (post-login redirects via ?next= are not used today but the import is
  // preserved to keep this chunk's diff minimal).
  // eslint-disable-next-line no-unused-vars
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    username: '',
    password: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      // The `username` field still carries the credential identifier. As of
      // Chunk 20 the value is school-email-shaped (e.g.
      // `ahmed2951@miskschools.edu.sa`), but it is NOT a real email — there
      // is no email integration, no SSO, no verification. The backend looks
      // it up in users.username verbatim. The field name is unchanged to
      // preserve the existing API contract (POST /auth/login { username }).
      const response = await auth.login(formData.username, formData.password);
      const { access_token, user } = response.data;

      setToken(access_token);
      setUser(user);

      // Redirect based on role
      if (user.role === 'student') {
        navigate('/dashboard/student');
      } else if (user.role === 'teacher') {
        navigate('/dashboard/teacher');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <h2>Login</h2>

        {error && <div className="error-message">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>School Email</label>
            <input
              type="email"
              name="username"
              value={formData.username}
              onChange={handleChange}
              autoComplete="username"
              required
              placeholder="name@miskschools.edu.sa"
            />
          </div>

          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              autoComplete="current-password"
              required
              placeholder="Enter your password"
            />
          </div>

          <button type="submit" className="btn-login" disabled={loading}>
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        {/*
          Demo credentials are hardcoded for the pre-buy-in demo. Suffixes
          are produced by random.seed(MISK_TRACKER_SEED) in backend
          database.py::seed_data() and are stable across reseeds. To verify
          or update after any seed change, run:
            sqlite3 backend/diploma_tracker.db \
              "SELECT username FROM users WHERE role='student' ORDER BY id LIMIT 1;"
            sqlite3 backend/diploma_tracker.db \
              "SELECT username FROM users WHERE role='teacher' ORDER BY id LIMIT 1;"
        */}
        <div className="demo-credentials">
          <strong>Demo Credentials:</strong><br />
          Student — Email: <code>ahmed2951@miskschools.edu.sa</code> Password: <code>password123</code><br />
          Teacher — Email: <code>mthomas@miskschools.edu.sa</code> Password: <code>password123</code>
        </div>
      </div>
    </div>
  );
}

export default LoginPage;