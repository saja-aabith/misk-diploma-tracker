import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { admin } from '../api/client';

// Admin console: create student and teacher accounts, see the roster, and
// reset passwords. Matches the existing institutional look (white cards on the
// deep-green background, shared .form-group / .btn-login / .error-message
// classes) rather than introducing a new visual style.

const MIN_PASSWORD_LEN = 8;
const MIN_GRADE = 4;
const MAX_GRADE = 12;
const GRADES = Array.from({ length: MAX_GRADE - MIN_GRADE + 1 }, (_, i) => MIN_GRADE + i);

// Tolerant error-detail extractor: the backend returns a string for legacy
// handlers, a {code, message} object for migrated handlers, and a list of
// {msg} objects for Pydantic validation (422). Accept all three.
function extractErrorMessage(err, fallback) {
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0];
    if (first && typeof first.msg === 'string') return first.msg;
  }
  if (detail && typeof detail === 'object' && typeof detail.message === 'string') {
    return detail.message;
  }
  return fallback;
}

const panelStyle = {
  background: '#ffffff',
  color: '#1a2e28',
  borderRadius: 10,
  padding: 20,
  marginBottom: 20,
  boxShadow: '0 2px 10px rgba(0,0,0,0.15)',
};

const labelMuted = { color: '#5a6b64', fontSize: 12 };

function AdminDashboard() {
  const navigate = useNavigate();

  const [users, setUsers] = useState([]);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [usersError, setUsersError] = useState('');

  // Create-account form state.
  const [role, setRole] = useState('student');
  const [fullName, setFullName] = useState('');
  const [usernameBase, setUsernameBase] = useState('');
  const [password, setPassword] = useState('');
  const [currentGrade, setCurrentGrade] = useState('');
  const [entryGrade, setEntryGrade] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');
  const [createdNotice, setCreatedNotice] = useState(null); // { username, role }

  // Reset-password inline state.
  const [resetUserId, setResetUserId] = useState(null);
  const [resetValue, setResetValue] = useState('');
  const [resetError, setResetError] = useState('');
  const [resetBusy, setResetBusy] = useState(false);
  const [resetNotice, setResetNotice] = useState('');

  const loadUsers = useCallback(() => {
    setLoadingUsers(true);
    setUsersError('');
    admin
      .listUsers()
      .then((res) => setUsers(res?.data?.users || []))
      .catch((err) =>
        setUsersError(extractErrorMessage(err, 'Could not load accounts.')))
      .finally(() => setLoadingUsers(false));
  }, []);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const resetForm = () => {
    setFullName('');
    setUsernameBase('');
    setPassword('');
    setCurrentGrade('');
    setEntryGrade('');
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setFormError('');
    setCreatedNotice(null);

    const cleanFullName = fullName.trim();
    const cleanBase = usernameBase.trim().toLowerCase();

    if (!cleanFullName) {
      setFormError('Enter the full name.');
      return;
    }
    if (!/^[a-z]+$/.test(cleanBase)) {
      setFormError('First name for the login must be letters only (a-z).');
      return;
    }
    if (password.length < MIN_PASSWORD_LEN) {
      setFormError(`Password must be at least ${MIN_PASSWORD_LEN} characters.`);
      return;
    }

    let cur = null;
    let ent = null;
    if (role === 'student') {
      cur = Number(currentGrade);
      ent = Number(entryGrade);
      if (!currentGrade || !entryGrade) {
        setFormError('Choose the current grade and the joining grade.');
        return;
      }
      if (ent > cur) {
        setFormError('Joining grade cannot be later than the current grade.');
        return;
      }
    }

    setSubmitting(true);
    try {
      const res = await admin.createUser({
        role,
        fullName: cleanFullName,
        usernameBase: cleanBase,
        password,
        currentGrade: role === 'student' ? cur : null,
        entryGrade: role === 'student' ? ent : null,
      });
      const created = res?.data;
      setCreatedNotice({ username: created?.username, role: created?.role });
      resetForm();
      loadUsers();
    } catch (err) {
      setFormError(extractErrorMessage(err, 'Could not create the account.'));
    } finally {
      setSubmitting(false);
    }
  };

  const openReset = (userId) => {
    setResetUserId(userId);
    setResetValue('');
    setResetError('');
    setResetNotice('');
  };

  const handleReset = async (userId) => {
    setResetError('');
    if (resetValue.length < MIN_PASSWORD_LEN) {
      setResetError(`Password must be at least ${MIN_PASSWORD_LEN} characters.`);
      return;
    }
    setResetBusy(true);
    try {
      await admin.resetPassword({ userId, newPassword: resetValue });
      setResetUserId(null);
      setResetValue('');
      setResetNotice('Password updated.');
    } catch (err) {
      setResetError(extractErrorMessage(err, 'Could not reset the password.'));
    } finally {
      setResetBusy(false);
    }
  };

  const handleLogout = () => {
    // misk_token / misk_user are the locked auth storage keys (utils/auth.js).
    // If utils/auth exposes a clearAuth()/logout() helper, prefer that here.
    localStorage.removeItem('misk_token');
    localStorage.removeItem('misk_user');
    navigate('/login');
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'linear-gradient(160deg, #1a5c45 0%, #0d3d2b 100%)',
        padding: '24px 16px',
      }}
    >
      <div style={{ maxWidth: 960, margin: '0 auto' }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 20,
          }}
        >
          <div>
            <h1 style={{ color: '#ffffff', margin: 0 }}>Admin</h1>
            <div style={{ color: 'rgba(255,255,255,0.75)', fontSize: 14 }}>
              Create accounts and manage passwords
            </div>
          </div>
          <button
            type="button"
            className="btn-login"
            style={{ width: 'auto', padding: '0 16px' }}
            onClick={handleLogout}
          >
            Log out
          </button>
        </div>

        {/* Create account */}
        <div style={panelStyle}>
          <h3 style={{ marginTop: 0 }}>Create an account</h3>

          {createdNotice && createdNotice.username && (
            <div
              className="success-message"
              style={{
                background: '#e8f5ee',
                border: '1px solid #2ECC71',
                borderRadius: 8,
                padding: 12,
                marginBottom: 12,
                color: '#1a2e28',
              }}
            >
              Account created. Login username:{' '}
              <strong>{createdNotice.username}</strong>. Give this and the
              password you set to the {createdNotice.role}.
            </div>
          )}

          {formError && <div className="error-message">{formError}</div>}

          <form onSubmit={handleCreate}>
            <div className="form-group">
              <label>Role</label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value)}
                disabled={submitting}
              >
                <option value="student">Student</option>
                <option value="teacher">Teacher</option>
              </select>
            </div>

            <div className="form-group">
              <label>Full name</label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="e.g. Faisal Al-Otaibi"
                disabled={submitting}
                required
              />
            </div>

            <div className="form-group">
              <label>First name for the login</label>
              <input
                type="text"
                value={usernameBase}
                onChange={(e) => setUsernameBase(e.target.value)}
                placeholder="e.g. faisal"
                disabled={submitting}
                required
              />
              <small style={labelMuted}>
                Letters only. The login is created as this name plus four digits,
                for example faisal4821@miskschools.edu.sa.
              </small>
            </div>

            <div className="form-group">
              <label>Password</label>
              <input
                type="text"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 8 characters"
                disabled={submitting}
                required
              />
              <small style={labelMuted}>
                Shown as text so you can read it back to the person. At least{' '}
                {MIN_PASSWORD_LEN} characters.
              </small>
            </div>

            {role === 'student' && (
              <div style={{ display: 'flex', gap: 12 }}>
                <div className="form-group" style={{ flex: 1 }}>
                  <label>Current grade</label>
                  <select
                    value={currentGrade}
                    onChange={(e) => setCurrentGrade(e.target.value)}
                    disabled={submitting}
                  >
                    <option value="" disabled>
                      Choose
                    </option>
                    {GRADES.map((g) => (
                      <option key={g} value={g}>
                        {g}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-group" style={{ flex: 1 }}>
                  <label>Joining grade</label>
                  <select
                    value={entryGrade}
                    onChange={(e) => setEntryGrade(e.target.value)}
                    disabled={submitting}
                  >
                    <option value="" disabled>
                      Choose
                    </option>
                    {GRADES.map((g) => (
                      <option key={g} value={g}>
                        {g}
                      </option>
                    ))}
                  </select>
                  <small style={labelMuted}>The grade they joined the school.</small>
                </div>
              </div>
            )}

            <button type="submit" className="btn-login" disabled={submitting}>
              {submitting ? 'Creating…' : 'Create account'}
            </button>
          </form>
        </div>

        {/* Accounts list */}
        <div style={panelStyle}>
          <h3 style={{ marginTop: 0 }}>Accounts</h3>

          {resetNotice && (
            <div
              style={{
                background: '#e8f5ee',
                border: '1px solid #2ECC71',
                borderRadius: 8,
                padding: 10,
                marginBottom: 12,
                color: '#1a2e28',
              }}
            >
              {resetNotice}
            </div>
          )}

          {loadingUsers && <div>Loading accounts…</div>}
          {usersError && <div className="error-message">{usersError}</div>}

          {!loadingUsers && !usersError && users.length === 0 && (
            <div style={labelMuted}>No student or teacher accounts yet.</div>
          )}

          {!loadingUsers && !usersError && users.length > 0 && (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
              <thead>
                <tr style={{ textAlign: 'left', borderBottom: '1px solid #d8e2dd' }}>
                  <th style={{ padding: '8px 6px' }}>Login</th>
                  <th style={{ padding: '8px 6px' }}>Name</th>
                  <th style={{ padding: '8px 6px' }}>Role</th>
                  <th style={{ padding: '8px 6px' }}>Grade</th>
                  <th style={{ padding: '8px 6px' }}></th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} style={{ borderBottom: '1px solid #eef3f1' }}>
                    <td style={{ padding: '8px 6px', wordBreak: 'break-all' }}>
                      {u.username}
                    </td>
                    <td style={{ padding: '8px 6px' }}>{u.full_name || '—'}</td>
                    <td style={{ padding: '8px 6px', textTransform: 'capitalize' }}>
                      {u.role}
                    </td>
                    <td style={{ padding: '8px 6px' }}>
                      {u.role === 'student'
                        ? `${u.current_grade ?? '—'} (joined ${u.entry_grade ?? '—'})`
                        : '—'}
                    </td>
                    <td style={{ padding: '8px 6px' }}>
                      {resetUserId === u.id ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                          <input
                            type="text"
                            value={resetValue}
                            onChange={(e) => setResetValue(e.target.value)}
                            placeholder="New password (min 8)"
                            disabled={resetBusy}
                          />
                          {resetError && (
                            <div className="error-message" style={{ margin: 0 }}>
                              {resetError}
                            </div>
                          )}
                          <div style={{ display: 'flex', gap: 6 }}>
                            <button
                              type="button"
                              className="btn-login"
                              style={{ width: 'auto', padding: '0 12px' }}
                              onClick={() => handleReset(u.id)}
                              disabled={resetBusy}
                            >
                              {resetBusy ? 'Saving…' : 'Save'}
                            </button>
                            <button
                              type="button"
                              onClick={() => setResetUserId(null)}
                              disabled={resetBusy}
                              style={{
                                background: 'transparent',
                                border: '1px solid #c2cec9',
                                borderRadius: 6,
                                cursor: 'pointer',
                              }}
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={() => openReset(u.id)}
                          style={{
                            background: 'transparent',
                            border: '1px solid #c2cec9',
                            borderRadius: 6,
                            padding: '4px 10px',
                            cursor: 'pointer',
                          }}
                        >
                          Reset password
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

export default AdminDashboard;
