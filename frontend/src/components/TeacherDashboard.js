import React, { useState, useEffect } from 'react';
import { teacher } from '../api/client';
import { getUser, logout } from '../utils/auth';
import AttachmentLink from './AttachmentLink';

// Tolerant error-detail extractor: backend returns a string for legacy
// handlers and a {code, message} dict for migrated handlers (Chunk 7).
// Used only by the new code paths in this file; existing handlers keep
// their current `error.response?.data?.detail` access pattern per the
// per-handler migration discipline.
function extractErrorMessage(err, fallback) {
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object') {
    if (typeof detail.message === 'string') return detail.message;
  }
  return fallback;
}

function TeacherDashboard() {
  const [activeTab, setActiveTab] = useState('review');
  const [submissions, setSubmissions] = useState([]);
  const [selectedSubmission, setSelectedSubmission] = useState(null);
  const [filter, setFilter] = useState('all');
  const [rating, setRating] = useState(0);
  const [feedback, setFeedback] = useState('');
  const [decision, setDecision] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [students, setStudents] = useState([]);
  const [selectedStudent, setSelectedStudent] = useState(null);
  const [studentReport, setStudentReport] = useState(null);
  const [loading, setLoading] = useState(true);

  // Student Profiles tab — separate state from Student Reports so the two
  // tabs don't clobber each other's selection or fetched payload.
  const [selectedProfileStudent, setSelectedProfileStudent] = useState(null);
  const [studentProfile, setStudentProfile] = useState(null);
  const [studentProfileError, setStudentProfileError] = useState('');
  const [studentProfileLoading, setStudentProfileLoading] = useState(false);

  const user = getUser();

  useEffect(() => {
    loadSubmissions();
    loadStudents();
  }, [filter]);

  const loadSubmissions = async () => {
    try {
      const response = await teacher.getSubmissions(filter);
      setSubmissions(response.data.submissions);
    } catch (error) {
      console.error('Failed to load submissions:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadStudents = async () => {
    try {
      const response = await teacher.getSubmissions('all');
      const uniqueStudents = [
        ...new Map(
          response.data.submissions.map((s) => [
            s.student_id,
            { id: s.student_id, name: s.student_name }
          ])
        ).values()
      ];
      setStudents(uniqueStudents);
    } catch (error) {
      console.error('Failed to load students:', error);
    }
  };

  const handleReviewClick = async (submission) => {
    try {
      const response = await teacher.getSubmissionDetail(submission.id);
      setSelectedSubmission(response.data);
      setRating(0);
      setFeedback('');
      setDecision('');
    } catch (error) {
      console.error('Failed to load submission details:', error);
    }
  };

  const handleSubmitReview = async (e) => {
    e.preventDefault();

    if (!decision) {
      alert('Please select approve or reject');
      return;
    }

    if (rating === 0) {
      alert('Please select a rating');
      return;
    }

    setSubmitting(true);

    try {
      await teacher.submitReview({
        submission_id: selectedSubmission.id,
        rating,
        decision,
        feedback
      });

      alert('Review submitted successfully!');
      setSelectedSubmission(null);
      setRating(0);
      setFeedback('');
      setDecision('');
      loadSubmissions();
    } catch (error) {
      alert(error.response?.data?.detail || 'Failed to submit review');
    } finally {
      setSubmitting(false);
    }
  };

  const handleStudentSelect = async (studentId) => {
    setSelectedStudent(studentId);
    try {
      const response = await teacher.getStudentReport(studentId);
      setStudentReport(response.data);
    } catch (error) {
      console.error('Failed to load student report:', error);
    }
  };

  // Student Profiles tab
  const loadStudentProfile = async (studentId) => {
    setStudentProfileLoading(true);
    setStudentProfileError('');
    try {
      const response = await teacher.getStudentProfile(studentId);
      setStudentProfile(response.data);
    } catch (error) {
      console.error('Failed to load student profile:', error);
      setStudentProfile(null);
      setStudentProfileError(extractErrorMessage(error, 'Could not load student profile.'));
    } finally {
      setStudentProfileLoading(false);
    }
  };

  const handleProfileStudentSelect = (studentId) => {
    setSelectedProfileStudent(studentId);
    if (studentId) {
      loadStudentProfile(studentId);
    } else {
      setStudentProfile(null);
      setStudentProfileError('');
    }
  };

  if (loading) {
    return <div className="loading">Loading...</div>;
  }

  const tabBase = {
    position: 'relative',
    padding: '14px 18px',
    fontWeight: 800,
    letterSpacing: '0.02em',
    fontSize: 16,
    color: 'rgba(255,255,255,0.85)'
  };

  const tabActive = {
    color: '#ffffff',
    textShadow: '0 2px 14px rgba(0,0,0,0.18)',
    filter: 'drop-shadow(0 10px 18px rgba(0,0,0,0.12))'
  };

  const tabInactive = {
    color: 'rgba(255,255,255,0.82)'
  };

  const activeUnderline = {
    content: '""',
    position: 'absolute',
    left: 10,
    right: 10,
    bottom: -8,
    height: 4,
    borderRadius: 999,
    background: 'rgba(255,255,255,0.9)',
    boxShadow: '0 10px 26px rgba(0,0,0,0.18), 0 0 22px rgba(255,255,255,0.24)'
  };

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <div className="container">
          <div className="dashboard-header-content">
            <div className="user-info">
              <h2>{user?.full_name || 'Teacher'}</h2>
              <p>Teacher Dashboard</p>
            </div>
            <button onClick={logout} className="btn-logout">
              Logout
            </button>
          </div>
        </div>
      </header>

      <div className="container">
        <div className="tabs">
          <button
            className={`tab ${activeTab === 'review' ? 'active' : ''}`}
            onClick={() => setActiveTab('review')}
            style={{ ...tabBase, ...(activeTab === 'review' ? tabActive : tabInactive) }}
          >
            Pending Reviews
            {activeTab === 'review' && <span style={activeUnderline} />}
          </button>

          <button
            className={`tab ${activeTab === 'report' ? 'active' : ''}`}
            onClick={() => setActiveTab('report')}
            style={{ ...tabBase, ...(activeTab === 'report' ? tabActive : tabInactive) }}
          >
            Student Reports
            {activeTab === 'report' && <span style={activeUnderline} />}
          </button>

          <button
            className={`tab ${activeTab === 'profile' ? 'active' : ''}`}
            onClick={() => setActiveTab('profile')}
            style={{ ...tabBase, ...(activeTab === 'profile' ? tabActive : tabInactive) }}
          >
            Student Profiles
            {activeTab === 'profile' && <span style={activeUnderline} />}
          </button>
        </div>

        {activeTab === 'review' && (
          <>
            <div className="filter-bar">
              <select value={filter} onChange={(e) => setFilter(e.target.value)}>
                <option value="all">All Submissions</option>
                <option value="submitted">Pending Review</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
              </select>
            </div>

            <div className="card">
              <h3>Review Queue ({submissions.length})</h3>
              <div className="review-queue">
                {submissions.map((submission) => (
                  <div key={submission.id} className="queue-item">
                    <div className="queue-info">
                      <h4>{submission.student_name}</h4>
                      <p>
                        {submission.objective_title} • {submission.quadrant_name}
                      </p>
                      <p style={{ fontSize: '14px', color: '#7f8c8d' }}>
                        {new Date(submission.submission_date).toLocaleDateString()} • Reviews:{' '}
                        {submission.review_status}
                      </p>
                    </div>
                    <button className="btn-review" onClick={() => handleReviewClick(submission)}>
                      Review
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        {activeTab === 'report' && (
          <>
            <div className="filter-bar">
              <select value={selectedStudent || ''} onChange={(e) => handleStudentSelect(e.target.value)}>
                <option value="">Select a student...</option>
                {students.map((student) => (
                  <option key={student.id} value={student.id}>
                    {student.name}
                  </option>
                ))}
              </select>
            </div>

            {studentReport && (
              <div className="card">
                <h3>{studentReport.student_name}'s Progress Report</h3>
                <div
                  style={{
                    textAlign: 'center',
                    fontSize: '32px',
                    fontWeight: 'bold',
                    color: '#2c3e50',
                    margin: '20px 0'
                  }}
                >
                  Overall: {studentReport.overall_completion_percentage}%
                </div>

                <div className="quadrant-info">
                  {studentReport.quadrant_reports.map((quadrant) => (
                    <div
                      key={quadrant.quadrant_id}
                      className="quadrant-card"
                      style={{ borderLeftColor: quadrant.color }}
                    >
                      <h4>{quadrant.quadrant_name}</h4>
                      <div className="completion" style={{ color: quadrant.color }}>
                        {quadrant.completion_percentage}%
                      </div>
                      <div className="progress-bar">
                        <div
                          className="progress-fill"
                          style={{
                            width: `${quadrant.completion_percentage}%`,
                            background: quadrant.color
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>

                <div style={{ marginTop: '24px' }}>
                  <h4>Submission Summary</h4>
                  <div className="objective-stats" style={{ marginTop: '12px' }}>
                    <span>Total: {studentReport.submission_summary.total_submitted}</span>
                    <span>Approved: {studentReport.submission_summary.total_approved}</span>
                    <span>Pending: {studentReport.submission_summary.pending_review}</span>
                    <span>Rejected: {studentReport.submission_summary.rejected}</span>
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {activeTab === 'profile' && (
          <>
            <div className="filter-bar">
              <select
                value={selectedProfileStudent || ''}
                onChange={(e) => handleProfileStudentSelect(e.target.value)}
              >
                <option value="">Select a student...</option>
                {students.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>

            {studentProfileError && (
              <div className="error-message" style={{ marginBottom: 12 }}>
                {studentProfileError}
              </div>
            )}

            {studentProfileLoading && <div className="loading">Loading profile…</div>}

            {studentProfile && !studentProfileLoading && (
              <div className="card">
                <h3>{studentProfile.student_name}</h3>
                <div style={{ color: '#5f6f6b', fontSize: 14, marginTop: -4 }}>
                  {studentProfile.email}
                </div>

                <div style={{ marginTop: 22, display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
                  <h4 style={{ margin: 0 }}>Misk Core — Activity Log</h4>
                  <span style={{ fontSize: 13, color: '#6d7f7a' }}>
                    {studentProfile.activities?.length || 0} entries
                  </span>
                </div>

                <div style={{ marginTop: 14 }}>
                  {(!studentProfile.activities || studentProfile.activities.length === 0) ? (
                    <div style={{ padding: 14, borderRadius: 12, background: 'rgba(0,0,0,0.03)' }}>
                      This student hasn't logged any Misk Core activities yet.
                    </div>
                  ) : (
                    <div style={{ display: 'grid', gap: 12 }}>
                      {studentProfile.activities.map((item) => (
                        <div
                          key={item.id}
                          style={{
                            borderRadius: 14,
                            padding: 14,
                            background: 'rgba(255,255,255,0.85)',
                            border: '1px solid rgba(0,0,0,0.06)',
                            boxShadow: '0 10px 28px rgba(0,0,0,0.06)',
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                            <span
                              style={{
                                fontSize: 12,
                                padding: '6px 10px',
                                borderRadius: 999,
                                background: 'rgba(2, 102, 75, 0.10)',
                                color: '#02664b',
                                fontWeight: 700,
                                letterSpacing: '0.02em',
                              }}
                            >
                              {item.category_name}
                            </span>
                            {item.activity_date && (
                              <span style={{ fontSize: 12, color: '#6d7f7a' }}>
                                {new Date(item.activity_date).toLocaleDateString()}
                              </span>
                            )}
                          </div>

                          <div style={{ marginTop: 8, fontSize: 16, fontWeight: 800, color: '#0b3f33' }}>
                            {item.title}
                          </div>

                          {item.description && (
                            <div style={{ marginTop: 6, color: '#3f534f', lineHeight: 1.45 }}>
                              {item.description}
                            </div>
                          )}

                          {Array.isArray(item.tags) && item.tags.length > 0 && (
                            <div style={{ marginTop: 10, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                              {item.tags.map((t) => (
                                <span
                                  key={t}
                                  style={{
                                    fontSize: 11,
                                    padding: '4px 8px',
                                    borderRadius: 999,
                                    background: 'rgba(0,0,0,0.05)',
                                    color: '#3f534f',
                                    fontWeight: 600,
                                  }}
                                >
                                  #{t}
                                </span>
                              ))}
                            </div>
                          )}

                          {item.stored_filename && (
                            <div style={{ marginTop: 10, fontSize: 13, color: '#4e615d' }}>
                              <AttachmentLink
                                storedFilename={item.stored_filename}
                                originalFilename={item.original_filename}
                              />
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {selectedSubmission && (
        <div className="modal-overlay" onClick={() => setSelectedSubmission(null)}>
          <div
            className="modal-content"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: '600px' }}
          >
            <div className="modal-header">
              <h3>Review Submission</h3>
              <button className="btn-close" onClick={() => setSelectedSubmission(null)}>
                ×
              </button>
            </div>

            <div style={{ marginBottom: '20px' }}>
              <h4>{selectedSubmission.student_name}</h4>
              <p>
                {selectedSubmission.objective_title} • {selectedSubmission.quadrant_name}
              </p>
              <p style={{ fontSize: '14px', color: '#7f8c8d' }}>
                Submitted: {new Date(selectedSubmission.submission_date).toLocaleString()}
              </p>
              <p style={{ fontSize: '14px', fontWeight: 'bold', color: '#667eea' }}>
                Approval Progress: {selectedSubmission.approval_progress}
              </p>
            </div>

            <div style={{ marginBottom: '20px', padding: '12px', background: '#f8f9fa', borderRadius: '8px' }}>
              <strong>File:</strong> {selectedSubmission.file_name}
              <br />
              {selectedSubmission.description && (
                <>
                  <strong>Description:</strong> {selectedSubmission.description}
                </>
              )}
            </div>

            {selectedSubmission.reviews.length > 0 && (
              <div style={{ marginBottom: '20px' }}>
                <h4>Previous Reviews:</h4>
                {selectedSubmission.reviews.map((review) => (
                  <div key={review.id} className="review-item">
                    <div className="review-header">
                      <span>{review.teacher_name}</span>
                      <span className="rating">{'★'.repeat(review.rating)}</span>
                    </div>
                    <div>{review.feedback}</div>
                    <div style={{ fontSize: '12px', color: '#7f8c8d', marginTop: '4px' }}>
                      {review.decision.toUpperCase()} • {new Date(review.reviewed_at).toLocaleString()}
                    </div>
                  </div>
                ))}
              </div>
            )}

            <form onSubmit={handleSubmitReview} className="review-form">
              <div className="form-group">
                <label>Rating</label>
                <div className="rating-selector">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <span
                      key={star}
                      className={`star ${star <= rating ? 'active' : ''}`}
                      onClick={() => setRating(star)}
                    >
                      ★
                    </span>
                  ))}
                </div>
              </div>

              <div className="form-group">
                <label>Feedback (Optional)</label>
                <textarea
                  value={feedback}
                  onChange={(e) => setFeedback(e.target.value)}
                  placeholder="Add your feedback..."
                />
              </div>

              <div className="decision-buttons">
                <button
                  type="button"
                  className={`btn-approve ${decision === 'approved' ? 'active' : ''}`}
                  style={{ opacity: decision === 'approved' ? 1 : 0.7 }}
                  onClick={() => setDecision('approved')}
                >
                  Approve
                </button>
                <button
                  type="button"
                  className={`btn-reject ${decision === 'rejected' ? 'active' : ''}`}
                  style={{ opacity: decision === 'rejected' ? 1 : 0.7 }}
                  onClick={() => setDecision('rejected')}
                >
                  Reject
                </button>
              </div>

              <button type="submit" className="btn-login" disabled={submitting} style={{ marginTop: '16px' }}>
                {submitting ? 'Submitting...' : 'Submit Review'}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default TeacherDashboard;