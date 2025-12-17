import React, { useState, useEffect } from 'react';
import { teacher } from '../api/client';
import { getUser, logout } from '../utils/auth';

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
    // Get unique students from submissions
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

  if (loading) {
    return <div className="loading">Loading...</div>;
  }

  // ✅ Make the tabs more visible (works even if CSS is weak)
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
