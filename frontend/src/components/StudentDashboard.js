import React, { useState, useEffect, useMemo } from 'react';
import { student } from '../api/client';
import { getUser, logout } from '../utils/auth';
import QuadrantCircle3D from './QuadrantCircle3D';
import UploadModal from './UploadModal';

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

const MISK_CORE_STORAGE_KEY = 'misk_core_timeline_v1';

function StudentDashboard() {
  const [dashboardData, setDashboardData] = useState(null);
  const [objectives, setObjectives] = useState([]);
  const [submissions, setSubmissions] = useState([]);
  const [selectedQuadrant, setSelectedQuadrant] = useState(null);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [selectedObjective, setSelectedObjective] = useState(null);
  const [activeTab, setActiveTab] = useState('progress');
  const [loading, setLoading] = useState(true);

  // ✅ Misk Core Timeline state
  const [miskCoreItems, setMiskCoreItems] = useState([]);
  const [showMiskCoreModal, setShowMiskCoreModal] = useState(false);
  const [mcTitle, setMcTitle] = useState('');
  const [mcType, setMcType] = useState('CCAP');
  const [mcDate, setMcDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [mcDesc, setMcDesc] = useState('');
  const [mcFile, setMcFile] = useState(null);
  const [mcSaving, setMcSaving] = useState(false);
  const [mcError, setMcError] = useState('');

  const user = getUser();

  useEffect(() => {
    loadDashboard();
    loadObjectives();
    loadSubmissions();
    loadMiskCoreTimeline();
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

  // ✅ Local timeline fallback
  const loadMiskCoreTimeline = () => {
    try {
      const raw = localStorage.getItem(MISK_CORE_STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) setMiskCoreItems(parsed);
    } catch (e) {
      console.warn('Failed to load Misk Core timeline from storage:', e);
    }
  };

  const persistMiskCoreTimeline = (items) => {
    try {
      localStorage.setItem(MISK_CORE_STORAGE_KEY, JSON.stringify(items));
    } catch (e) {
      console.warn('Failed to save Misk Core timeline to storage:', e);
    }
  };

  const sortedMiskCoreItems = useMemo(() => {
    return [...miskCoreItems].sort((a, b) => new Date(b.date) - new Date(a.date));
  }, [miskCoreItems]);

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

  // ✅ Add a timeline entry (tries backend endpoint if you add it later)
  const handleSaveMiskCore = async (e) => {
    e.preventDefault();
    setMcError('');

    if (!mcTitle.trim()) {
      setMcError('Please enter a title (e.g., CCAP Event, Trip, Competition, Project 10).');
      return;
    }

    setMcSaving(true);

    const newItem = {
      id: `${Date.now()}_${Math.random().toString(16).slice(2)}`,
      title: mcTitle.trim(),
      type: mcType,
      date: mcDate,
      description: mcDesc.trim(),
      fileName: mcFile?.name || '',
      createdAt: new Date().toISOString(),
    };

    try {
      // If you later add an API method, this will use it automatically:
      // student.uploadMiskCoreExperience(formData)
      if (typeof student.uploadMiskCoreExperience === 'function') {
        const formData = new FormData();
        formData.append('title', newItem.title);
        formData.append('type', newItem.type);
        formData.append('date', newItem.date);
        formData.append('description', newItem.description);
        if (mcFile) formData.append('file', mcFile);

        await student.uploadMiskCoreExperience(formData);

        // If backend returns updated items, you can fetch here.
        // For now we also add locally for instant UI feedback:
      }

      const updated = [newItem, ...miskCoreItems];
      setMiskCoreItems(updated);
      persistMiskCoreTimeline(updated);

      // reset
      setShowMiskCoreModal(false);
      setMcTitle('');
      setMcType('CCAP');
      setMcDate(new Date().toISOString().slice(0, 10));
      setMcDesc('');
      setMcFile(null);
    } catch (err) {
      console.error(err);
      setMcError(err.response?.data?.detail || 'Failed to save experience.');
    } finally {
      setMcSaving(false);
    }
  };

  const handleDeleteMiskCoreItem = (id) => {
    const updated = miskCoreItems.filter((x) => x.id !== id);
    setMiskCoreItems(updated);
    persistMiskCoreTimeline(updated);
  };

  if (loading) return <div className="loading">Loading...</div>;

  const overallPct = clampPercent(dashboardData?.overall_completion_percentage);

  // ✅ Tab styles: more visible text
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
            {/* Main Progress Card (existing) */}
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
                <QuadrantCircle3D size={400} />
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

            {/* ✅ NEW: MISK CORE TIMELINE (no % meter) */}
            <div className="card">
              <div className="card-header-inline">
                <h3>Misk Core — Experiences Timeline</h3>
                <button
                  className="btn-upload"
                  style={{ maxWidth: 220 }}
                  onClick={() => setShowMiskCoreModal(true)}
                >
                  Add Experience
                </button>
              </div>

              <div style={{ marginTop: 6, color: '#5f6f6b', fontSize: 14 }}>
                Track CCAP, trips, competitions, Project 10, and other experiences linked to all four quadrants.
              </div>

              <div style={{ marginTop: 18 }}>
                {sortedMiskCoreItems.length === 0 ? (
                  <div style={{ padding: 14, borderRadius: 12, background: 'rgba(0,0,0,0.03)' }}>
                    No Misk Core experiences yet — click <strong>Add Experience</strong> to start your timeline.
                  </div>
                ) : (
                  <div style={{ display: 'grid', gap: 12 }}>
                    {sortedMiskCoreItems.map((item) => (
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
                              {item.type}
                            </span>
                            <span style={{ fontSize: 12, color: '#6d7f7a' }}>
                              {new Date(item.date).toLocaleDateString()}
                            </span>
                          </div>

                          <button
                            onClick={() => handleDeleteMiskCoreItem(item.id)}
                            style={{
                              border: 'none',
                              background: 'transparent',
                              color: '#9aa7a3',
                              cursor: 'pointer',
                              fontWeight: 700,
                            }}
                            title="Remove from timeline"
                          >
                            ✕
                          </button>
                        </div>

                        <div style={{ marginTop: 8, fontSize: 16, fontWeight: 800, color: '#0b3f33' }}>
                          {item.title}
                        </div>

                        {item.description && (
                          <div style={{ marginTop: 6, color: '#3f534f', lineHeight: 1.45 }}>
                            {item.description}
                          </div>
                        )}

                        {item.fileName && (
                          <div style={{ marginTop: 10, fontSize: 13, color: '#4e615d' }}>
                            Attachment: <strong>{item.fileName}</strong>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Objectives (existing) */}
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

                  <div className="submission-meta">File: {submission.file_name}</div>

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

      {/* Existing Objective Upload Modal */}
      {showUploadModal && (
        <UploadModal
          objective={selectedObjective}
          onClose={() => setShowUploadModal(false)}
          onSuccess={handleUploadSuccess}
        />
      )}

      {/* ✅ NEW: Misk Core Add Experience Modal */}
      {showMiskCoreModal && (
        <div className="modal-overlay" onClick={() => setShowMiskCoreModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 640 }}>
            <div className="modal-header">
              <h3>Add Misk Core Experience</h3>
              <button className="btn-close" onClick={() => setShowMiskCoreModal(false)}>
                ×
              </button>
            </div>

            {mcError && <div className="error-message">{mcError}</div>}

            <form onSubmit={handleSaveMiskCore}>
              <div className="form-group">
                <label>Type</label>
                <select value={mcType} onChange={(e) => setMcType(e.target.value)}>
                  <option value="CCAP">CCAP</option>
                  <option value="Trip">Trip</option>
                  <option value="Competition">Competition</option>
                  <option value="Project 10">Project 10</option>
                  <option value="Volunteering">Volunteering</option>
                  <option value="Workshop">Workshop</option>
                  <option value="Other">Other</option>
                </select>
              </div>

              <div className="form-group">
                <label>Date</label>
                <input type="date" value={mcDate} onChange={(e) => setMcDate(e.target.value)} />
              </div>

              <div className="form-group">
                <label>Title</label>
                <input
                  type="text"
                  value={mcTitle}
                  onChange={(e) => setMcTitle(e.target.value)}
                  placeholder="e.g., CCAP Leadership Summit, National Museum Trip, Math Olympiad, Project 10 Showcase..."
                />
              </div>

              <div className="form-group">
                <label>Description (Optional)</label>
                <textarea
                  value={mcDesc}
                  onChange={(e) => setMcDesc(e.target.value)}
                  placeholder="What did you do? What was your role? Any outcomes/awards?"
                />
              </div>

              <div className="form-group">
                <label>Attachment (Optional)</label>
                <input
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png,.docx,.mp4,.pptx"
                  onChange={(e) => setMcFile(e.target.files[0])}
                />
                <small style={{ color: '#7f8c8d' }}>
                  Allowed: PDF, JPG, PNG, DOCX, MP4, PPTX
                </small>
              </div>

              <button type="submit" className="btn-login" disabled={mcSaving}>
                {mcSaving ? 'Saving...' : 'Save Experience'}
              </button>

              <div style={{ marginTop: 10, fontSize: 12, color: '#7f8c8d' }}>
                Note: If your backend endpoint isn’t added yet, this timeline is saved locally on this device.
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default StudentDashboard;
