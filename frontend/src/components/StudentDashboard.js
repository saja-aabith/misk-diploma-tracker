import React, { useState, useEffect } from 'react';
import { student } from '../api/client';
import { getUser, logout } from '../utils/auth';
import QuadrantCircle3D from './QuadrantCircle3D';
import UploadModal from './UploadModal';

function StudentDashboard() {
  const [dashboardData, setDashboardData] = useState(null);
  const [objectives, setObjectives] = useState([]);
  const [submissions, setSubmissions] = useState([]);
  const [selectedQuadrant, setSelectedQuadrant] = useState(null);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [selectedObjective, setSelectedObjective] = useState(null);
  const [activeTab, setActiveTab] = useState('progress');
  const [loading, setLoading] = useState(true);

  const user = getUser();

  useEffect(() => {
    loadDashboard();
    loadObjectives();
    loadSubmissions();
  }, []);

  const loadDashboard = async () => {
    try {
      const response = await student.getDashboard();
      setDashboardData(response.data);
    } catch (error) {
      console.error('Failed to load dashboard:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadObjectives = async (quadrantId = null) => {
    try {
      const response = await student.getObjectives(quadrantId);
      setObjectives(response.data.objectives);
    } catch (error) {
      console.error('Failed to load objectives:', error);
    }
  };

  const loadSubmissions = async () => {
    try {
      const response = await student.getSubmissions();
      setSubmissions(response.data.submissions);
    } catch (error) {
      console.error('Failed to load submissions:', error);
    }
  };

  const handleQuadrantClick = (quadrant) => {
    setSelectedQuadrant(quadrant);
    loadObjectives(quadrant.id);
  };

  const handleUploadClick = (objective) => {
    setSelectedObjective(objective);
    setShowUploadModal(true);
  };

  const handleUploadSuccess = () => {
    setShowUploadModal(false);
    loadDashboard();
    loadObjectives(selectedQuadrant?.id);
    loadSubmissions();
  };

  if (loading) {
    return <div className="loading">Loading...</div>;
  }

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <div className="container">
          <div className="dashboard-header-content">
            <div className="user-info">
              <h2>{dashboardData?.student_name}</h2>
              <p>Student Dashboard</p>
            </div>
            <button onClick={logout} className="btn-logout">Logout</button>
          </div>
        </div>
      </header>

      <div className="container">
        <div className="tabs">
          <button 
            className={`tab ${activeTab === 'progress' ? 'active' : ''}`}
            onClick={() => setActiveTab('progress')}
          >
            My Progress
          </button>
          <button 
            className={`tab ${activeTab === 'submissions' ? 'active' : ''}`}
            onClick={() => setActiveTab('submissions')}
          >
            My Submissions
          </button>
        </div>

        {activeTab === 'progress' && (
          <>
            <div className="card">
              <h3>Your Diploma Progress</h3>
              <div style={{ display: 'flex', justifyContent: 'center', margin: '20px 0' }}>
                <QuadrantCircle3D size={400} />
              </div>
              <div style={{ textAlign: 'center', fontSize: '24px', fontWeight: 'bold', color: '#2c3e50' }}>
                Overall Completion: {dashboardData?.overall_completion_percentage}%
              </div>

              <div className="quadrant-info">
                {dashboardData?.quadrants.map((quadrant) => (
                  <div
                    key={quadrant.id}
                    className="quadrant-card"
                    style={{ borderLeftColor: quadrant.color }}
                    onClick={() => handleQuadrantClick(quadrant)}
                  >
                    <h4>{quadrant.name}</h4>
                    <div className="completion" style={{ color: quadrant.color }}>
                      {quadrant.completion_percentage}%
                    </div>
                    <div className="progress-bar">
                      <div
                        className="progress-fill"
                        style={{
                          width: `${quadrant.completion_percentage}%`,
                          background: quadrant.color,
                        }}
                      />
                    </div>
                    <div className="progress-text">
                      {quadrant.objectives_completed} of {quadrant.total_objectives} completed
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {selectedQuadrant && objectives.length > 0 && (
              <div className="card">
                <h3>{selectedQuadrant.name} - Objectives</h3>
                <div className="objectives-list">
                  {objectives.map((objective) => (
                    <div
                      key={objective.id}
                      className="objective-card"
                      style={{ borderLeftColor: selectedQuadrant.color }}
                    >
                      <div className="objective-header">
                        <div className="objective-title">{objective.title}</div>
                        <span className={`status-badge status-${objective.status}`}>
                          {objective.status.replace('_', ' ')}
                        </span>
                      </div>
                      <div className="objective-description">{objective.description}</div>
                      <div className="progress-bar">
                        <div
                          className="progress-fill"
                          style={{
                            width: `${objective.completion_percentage}%`,
                            background: selectedQuadrant.color,
                          }}
                        />
                      </div>
                      <div className="objective-stats">
                        <span>{objective.current_points}/{objective.max_points} points</span>
                        <span>{objective.submission_count} submissions, {objective.approved_count} approved</span>
                      </div>
                      <button
                        className="btn-upload"
                        onClick={() => handleUploadClick(objective)}
                      >
                        Upload Evidence
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {activeTab === 'submissions' && (
          <div className="card">
            <h3>My Submissions</h3>
            <div className="submissions-list">
              {submissions.map((submission) => (
                <div key={submission.id} className="submission-card">
                  <div className="submission-header">
                    <div className="submission-title">{submission.objective_title}</div>
                    <span className={`status-badge status-${submission.status}`}>
                      {submission.status.replace('_', ' ')}
                    </span>
                  </div>
                  <div className="submission-meta">
                    {submission.quadrant_name} • {new Date(submission.submission_date).toLocaleDateString()}
                  </div>
                  <div className="submission-meta">
                    File: {submission.file_name}
                  </div>
                  {submission.description && (
                    <div className="submission-meta">Description: {submission.description}</div>
                  )}
                  {submission.reviews.length > 0 && (
                    <div className="reviews-section">
                      <strong>Reviews ({submission.reviews.length}):</strong>
                      {submission.reviews.map((review) => (
                        <div key={review.id} className="review-item">
                          <div className="review-header">
                            <span>{review.teacher_name}</span>
                            <span className="rating">{'★'.repeat(review.rating)}</span>
                          </div>
                          <div>{review.feedback}</div>
                          <div style={{ fontSize: '12px', color: '#7f8c8d', marginTop: '4px' }}>
                            {review.decision.toUpperCase()} • {new Date(review.reviewed_at).toLocaleDateString()}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {showUploadModal && (
        <UploadModal
          objective={selectedObjective}
          onClose={() => setShowUploadModal(false)}
          onSuccess={handleUploadSuccess}
        />
      )}
    </div>
  );
}

export default StudentDashboard;