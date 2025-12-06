import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { auth } from '../api/client';
import { setToken, setUser } from '../utils/auth';

function LoginPage() {
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
            <label>Username</label>
            <input
              type="text"
              name="username"
              value={formData.username}
              onChange={handleChange}
              required
              placeholder="Enter your username"
            />
          </div>

          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              required
              placeholder="Enter your password"
            />
          </div>

          <button type="submit" className="btn-login" disabled={loading}>
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        <div className="demo-credentials">
          <strong>Demo Credentials:</strong><br />
          Student - Username: <code>student1</code> Password: <code>password123</code><br />
          Teacher - Username: <code>teacher1</code> Password: <code>password123</code>
        </div>
      </div>
    </div>
  );
}

export default LoginPage;