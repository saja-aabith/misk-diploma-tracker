import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { student } from '../api/client';
import { getUser, logout } from '../utils/auth';
import QuadrantCircle3D from './QuadrantCircle3D';
import UploadModal from './UploadModal';
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

  // Ref to the objectives panel. Used to scroll the panel into view when a
  // quadrant is selected — both from a PillarProgressCard click and from the
  // Misk Core center click on the circle. The objectives panel only renders
  // when selectedQuadrant && objectives.length > 0, so we set the ref on
  // that block and rely on the brief render-then-scroll sequence below.
  const objectivesPanelRef = useRef(null);

  // user kept for parity with original (unused locally)
  // eslint-disable-next-line no-unused-vars
  const user = getUser();

  useEffect(() => {
    loadDashboard();
    loadObjectives();
    loadSubmissions();
    // Misk Core activity log has been retired in favour of structured
    // submissions under the Misk Core quadrant (Chunk 22). The backend
    // /student/activities routes still exist but are no longer consumed
    // here; they will be removed in a later cleanup chunk.
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

  // Scroll the objectives panel into view. Called after selecting a
  // quadrant. Uses a small timeout so React has a chance to render the
  // objectives panel before we measure / scroll. behavior:'smooth' for a
  // calmer transition; block:'start' keeps the heading visible.
  const scrollToObjectives = useCallback(() => {
    setTimeout(() => {
      if (objectivesPanelRef.current) {
        objectivesPanelRef.current.scrollIntoView({
          behavior: 'smooth',
          block: 'start',
        });
      }
    }, 100);
  }, []);

  const handleQuadrantClick = useCallback(
    (quadrant) => {
      setSelectedQuadrant(quadrant);
      loadObjectives(quadrant.id);
      scrollToObjectives();
    },
    [scrollToObjectives]
  );

  // Center click on the quadrant circle. Resolves the Misk Core quadrant
  // from dashboardData by name (the literal "Misk Core" set in the seed),
  // then routes through handleQuadrantClick so the behaviour is identical
  // to clicking a PillarProgressCard.
  //
  // Lookup is by name, not id, so the code stays correct if the AUTOINCREMENT
  // id assignment ever changes. If lookup fails (e.g. on a malformed DB),
  // we log and no-op rather than blowing up the dashboard.
  const selectMiskCore = useCallback(() => {
    const quadrants = dashboardData?.quadrants || [];
    const miskCore = quadrants.find((q) => q.name === 'Misk Core');
    if (!miskCore) {
      console.warn(
        'selectMiskCore: no quadrant named "Misk Core" in dashboard data; ' +
          'check backend seed.'
      );
      return;
    }
    handleQuadrantClick(miskCore);
  }, [dashboardData, handleQuadrantClick]);

  // Build the completion map for QuadrantCircle3D from the dashboard data.
  // Memoised so the prop reference is stable across renders that don't
  // change the underlying quadrant data; this avoids re-firing the
  // animation effect inside QuadrantCircle3D on unrelated re-renders.
  const completionByName = useMemo(() => {
    const list = dashboardData?.quadrants || [];
    return list.reduce((acc, q) => {
      acc[q.name] = q.completion_percentage;
      return acc;
    }, {});
  }, [dashboardData]);

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
                  onMiskCoreClick={selectMiskCore}
                  completionByName={completionByName}
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

            {selectedQuadrant && objectives.length > 0 && (
              <div className="card" ref={objectivesPanelRef}>
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
    </div>
  );
}

export default StudentDashboard;