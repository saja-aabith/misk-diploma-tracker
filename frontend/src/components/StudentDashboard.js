import React, { useState, useEffect } from 'react';
import { student } from '../api/client';
import { getUser, logout } from '../utils/auth';
import QuadrantCircle3D from './QuadrantCircle3D';
import UploadModal from './UploadModal';
import ActivityLogModal from './ActivityLogModal';
import AttachmentLink from './AttachmentLink';

/**
 * Helper: clamp any % between 0 and 100
 */
const clampPercent = (value) => {
  const num = Number(value) || 0;
  return Math.max(0, Math.min(num, 100));
};

/**
 * Futuristic horizontal meter for a quadrant / pillar
 */
const PillarProgressCard = ({ quadrant, onClick }) => {
  const pct = clampPercent(quadrant.completion_percentage);

  return (
    <div
      className="quadrant-card quadrant-card--modern"
      style={{ borderLeftColor: quadrant.color }}
      onClick={onClick}
    >
      <div className="quadrant-card-header">
        <div>
          <h4>{quadrant.name}</h4>
          <div className="quadrant-card-subtitle">
            {quadrant.objectives_completed} of {quadrant.total_objectives} completed
          </div>
        </div>
        <div className="quadrant-chip-percent" style={{ '--pillar-color': quadrant.color }}>
          {pct.toFixed(1)}%
        </div>
      </div>

      <div className="pillar-meter">
        <div className="pillar-meter-track" />
        <div className="pillar-meter-fill" style={{ '--pillar-color': quadrant.color, width: `${pct}%` }} />
        <div className="pillar-meter-thumb" style={{ '--pillar-color': quadrant.color, left: `${pct}%` }}>
          <span>{Math.round(pct)}%</span>
        </div>
      </div>
    </div>
  );
};

/**
 * Futuristic meter for an individual objective
 */
const ObjectiveProgressMeter = ({ percent, color }) => {
  const pct = clampPercent(percent);

  return (
    <div className="objective-meter">
      <div className="objective-meter-track" />
      <div className="objective-meter-fill" style={{ '--objective-color': color, width: `${pct}%` }} />
      <div className="objective-meter-dot" style={{ '--objective-color': color, left: `${pct}%` }} />
    </div>
  );
};

function StudentDashboard() {
  const [dashboardData, setDashboardData] = useState(null);
  const [objectives, setObjectives] = useState([]);
  const [submissions, setSubmissions] = useState([]);
  const [selectedQuadrant, setSelectedQuadrant] = useState(null);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [selectedObjective, setSelectedObjective] = useState(null);
  const [activeTab, setActiveTab] = useState('progress');
  const [loading, setLoading] = useState(true);

  // Misk Core (backend-backed)
  const [activities, setActivities] = useState([]);
  const [activitiesError, setActivitiesError] = useState('');
  const [showActivityModal, setShowActivityModal] = useState(false);

  // user kept for parity with original (unused locally)
  // eslint-disable-next-line no-unused-vars
  const user = getUser();

  useEffect(() => {
    loadDashboard();
    loadObjectives();
    loadSubmissions();
    loadActivities();
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

  const loadActivities = async () => {
    try {
      const response = await student.getActivities();
      setActivities(response?.data?.activities || []);
      setActivitiesError('');
    } catch (error) {
      console.error('Failed to load activities:', error);
      setActivitiesError('Could not load activities.');
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
    if (selectedQuadrant?.id) loadObjectives(selectedQuadrant.id);
    loadSubmissions();
  };

  const handleActivitySuccess = (newActivity) => {
    setShowActivityModal(false);
    if (newActivity && newActivity.id) {
      setActivities((prev) => [newActivity, ...prev]);
    }
    loadActivities();
  };

  if (loading) return <div className="loading">Loading...</div>;

  const overallPct = clampPercent(dashboardData?.overall_completion_percentage);

  const tabBaseStyle = {
    color: 'rgba(255,255,255,0.88)',
    fontWeight: 700,
    letterSpacing: '0.02em',
  };
  const tabActiveStyle = {
    color: '#ffffff',
    textShadow: '0 2px 10px rgba(0,0,0,0.18)',
  };
  const tabInactiveStyle = {
    color: 'rgba(255,255,255,0.78)',
  };

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <div className="container">
          <div className="dashboard-header-content">
            <div className="user-info">
              <h2>{dashboardData?.student_name}</h2>
              <p>Student Dashboard</p>
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
            className={`tab ${activeTab === 'progress' ? 'active' : ''}`}
            style={{
              ...tabBaseStyle,
              ...(activeTab === 'progress' ? tabActiveStyle : tabInactiveStyle),
            }}
            onClick={() => setActiveTab('progress')}
          >
            My Progress
          </button>

          <button
            className={`tab ${activeTab === 'submissions' ? 'active' : ''}`}
            style={{
              ...tabBaseStyle,
              ...(activeTab === 'submissions' ? tabActiveStyle : tabInactiveStyle),
            }}
            onClick={() => setActiveTab('submissions')}
          >
            My Submissions
          </button>
        </div>

        {activeTab === 'progress' && (
          <>
            <div className="card">
              <div className="card-header-inline">
                <h3>Your Diploma Progress</h3>

                <div className="overall-meter">
                  <span className="overall-label">Overall completion</span>
                  <span className="overall-value">{overallPct.toFixed(1)}%</span>
                  <div className="overall-bar">
                    <div className="overall-bar-track" />
                    <div className="overall-bar-fill" style={{ width: `${overallPct}%` }} />
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'center', margin: '26px 0 10px' }}>
                <QuadrantCircle3D
                  size={400}
                  onMiskCoreClick={() => setShowActivityModal(true)}
                />
              </div>

              <div className="quadrant-info quadrant-info--modern">
                {(dashboardData?.quadrants || []).map((quadrant) => (
                  <PillarProgressCard
                    key={quadrant.id}
                    quadrant={quadrant}
                    onClick={() => handleQuadrantClick(quadrant)}
                  />
                ))}
              </div>
            </div>

            <div className="card">
              <div className="card-header-inline">
                <h3>Misk Core — Activity Log</h3>
                <button
                  className="btn-upload"
                  style={{ maxWidth: 220 }}
                  onClick={() => setShowActivityModal(true)}
                >
                  Add Experience
                </button>
              </div>

              <div style={{ marginTop: 6, color: '#5f6f6b', fontSize: 14 }}>
                Track CCAP, trips, competitions, Project 10, and other experiences linked to all four quadrants.
              </div>

              {activitiesError && (
                <div className="error-message" style={{ marginTop: 12 }}>
                  {activitiesError}
                </div>
              )}

              <div style={{ marginTop: 18 }}>
                {activities.length === 0 ? (
                  <div style={{ padding: 14, borderRadius: 12, background: 'rgba(0,0,0,0.03)' }}>
                    No Misk Core activities yet — click <strong>Add Experience</strong> to start your log.
                  </div>
                ) : (
                  <div style={{ display: 'grid', gap: 12 }}>
                    {activities.map((item) => (
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
                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
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

            {selectedQuadrant && objectives.length > 0 && (
              <div className="card">
                <h3>{selectedQuadrant.name} – Objectives</h3>
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

                      <ObjectiveProgressMeter
                        percent={objective.completion_percentage}
                        color={selectedQuadrant.color}
                      />

                      <div className="objective-stats">
                        <span>
                          {objective.current_points}/{objective.max_points} points
                        </span>
                        <span>
                          {objective.submission_count} submissions, {objective.approved_count} approved
                        </span>
                      </div>

                      <button className="btn-upload" onClick={() => handleUploadClick(objective)}>
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
                    {submission.stored_filename && (
                      <>
                        {' '}
                        <AttachmentLink
                          storedFilename={submission.stored_filename}
                          originalFilename={submission.file_name}
                        />
                      </>
                    )}
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

      {showActivityModal && (
        <ActivityLogModal
          onClose={() => setShowActivityModal(false)}
          onSuccess={handleActivitySuccess}
        />
      )}
    </div>
  );
}

export default StudentDashboard;