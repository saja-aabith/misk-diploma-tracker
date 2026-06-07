import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { student } from '../api/client';
import { getUser, logout } from '../utils/auth';
import QuadrantCircle3D from './QuadrantCircle3D';
import UploadModal from './UploadModal';
import ActivityLogModal from './ActivityLogModal';
import AttachmentLink from './AttachmentLink';
import JourneyTimeline from './JourneyTimeline';
import DiplomaIdentityPanel from './DiplomaIdentityPanel';

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

/**
 * Formal Diploma status card (Chunk 31) — calm institutional banner at the
 * top of the My Progress tab. Read-only graduation view: shows the awarded
 * band once a teacher records one, an "all requirements met" state when the
 * student is eligible but not yet awarded, or an in-progress state otherwise.
 * The band is never computed client-side.
 */
const DiplomaStatusCard = ({ diploma }) => {
  const award = diploma?.award || null;
  const eligible = !!diploma?.eligible_for_diploma;

  let accent;
  let headline;
  let sub;
  if (award) {
    accent = '#F39C12';
    headline = `MISK Diploma — ${award.award_level}`;
    sub = award.selected_at
      ? `Awarded ${new Date(award.selected_at).toLocaleDateString()}`
      : 'Awarded';
  } else if (eligible) {
    accent = '#2ECC71';
    headline = 'All requirements met';
    sub = 'Your formal diploma decision is pending.';
  } else {
    accent = 'rgba(255,255,255,0.45)';
    headline = 'Formal Diploma — In Progress';
    sub = 'Complete all mandatory objectives to become eligible.';
  }

  return (
    <div className="card" style={{ borderLeft: `4px solid ${accent}` }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' }}>
        <h3 style={{ margin: 0 }}>{headline}</h3>
        <span style={{ color: '#6d7f7a', fontSize: 14 }}>{sub}</span>
      </div>
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
  const [diploma, setDiploma] = useState(null);
  const [activities, setActivities] = useState([]);
  const [showActivityModal, setShowActivityModal] = useState(false);

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
    loadDiploma();
    loadActivities();
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

  const loadDiploma = async () => {
    try {
      const response = await student.getDiplomaAward();
      setDiploma(response.data);
    } catch (error) {
      console.error('Failed to load diploma award:', error);
    }
  };

  const loadActivities = async () => {
    try {
      const response = await student.getActivities();
      setActivities(response.data.activities);
    } catch (error) {
      console.error('Failed to load activities:', error);
    }
  };

  const handleActivitySuccess = () => {
    setShowActivityModal(false);
    loadActivities();
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
      // Misk Core is now the open-ended activity area (its objectives were
      // deactivated in the restructure), so route it to the Misk Core tab
      // instead of an empty objectives drill-down.
      if (quadrant?.name === 'Misk Core') {
        setActiveTab('miskcore');
        return;
      }
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
    loadDiploma();
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

          <button
            className={`tab ${activeTab === 'miskcore' ? 'active' : ''}`}
            style={{
              ...tabBaseStyle,
              ...(activeTab === 'miskcore' ? tabActiveStyle : tabInactiveStyle),
            }}
            onClick={() => setActiveTab('miskcore')}
          >
            Misk Core
          </button>
        </div>

        {activeTab === 'progress' && (
          <>
            {diploma && <DiplomaStatusCard diploma={diploma} />}

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

              {/* Diploma Identity panel sits beside the quadrant circle on
                  desktop, stacks above it on mobile. Layout lives in
                  DiplomaIdentityPanel.css under .diploma-stage. */}
              <div className="diploma-stage">
                <DiplomaIdentityPanel
                  studentName={dashboardData?.student_name}
                  overallCompletion={dashboardData?.overall_completion_percentage}
                />
                <div className="diploma-stage-circle">
                  <QuadrantCircle3D
                    size={400}
                    onMiskCoreClick={selectMiskCore}
                    completionByName={completionByName}
                  />
                </div>
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

            {/* MISK Journey timeline (Chunk 25) — sits between the
                quadrant circle card and the objectives drill-down panel. */}
            <JourneyTimeline />

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

        {activeTab === 'miskcore' && (
          <div className="card">
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: 12,
              }}
            >
              <h3 style={{ margin: 0 }}>Misk Core Activities</h3>
              <button className="btn-upload" onClick={() => setShowActivityModal(true)}>
                Log Activity
              </button>
            </div>
            <p style={{ color: 'rgba(255,255,255,0.75)', marginTop: 8 }}>
              Log your wider achievements — competitions, community service, trips,
              and more. A teacher reviews each one before it's approved.
            </p>

            <div className="submissions-list">
              {activities.length === 0 && (
                <div style={{ color: 'rgba(255,255,255,0.7)' }}>
                  No activities logged yet.
                </div>
              )}
              {activities.map((activity) => (
                <div key={activity.id} className="submission-card">
                  <div className="submission-header">
                    <div className="submission-title">{activity.title}</div>
                    <span className={`status-badge status-${activity.status}`}>
                      {activity.status.replace('_', ' ')}
                    </span>
                  </div>

                  <div className="submission-meta">
                    {activity.category_name}
                    {activity.activity_date && (
                      <> • {new Date(activity.activity_date).toLocaleDateString()}</>
                    )}
                  </div>

                  {activity.description && (
                    <div className="submission-meta">{activity.description}</div>
                  )}

                  {activity.tags && activity.tags.length > 0 && (
                    <div className="submission-meta">Tags: {activity.tags.join(', ')}</div>
                  )}

                  {activity.stored_filename && (
                    <div className="submission-meta">
                      File: {activity.original_filename}{' '}
                      <AttachmentLink
                        storedFilename={activity.stored_filename}
                        originalFilename={activity.original_filename}
                      />
                    </div>
                  )}

                  {activity.review_feedback && (
                    <div className="submission-meta">
                      Teacher feedback: {activity.review_feedback}
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