import React, { useState, useEffect } from 'react';
import { teacher } from '../api/client';
import { getUser, logout } from '../utils/auth';
import AttachmentLink from './AttachmentLink';
import SkillsRadar from './SkillsRadar';

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

// ---------------------------------------------------------------------------
// Chunk 31 — result capture + manual diploma award (Student Reports tab)
// ---------------------------------------------------------------------------
// These constants are presentational only: they drive which input a result
// objective shows and provide fast client-side feedback. The backend
// (routes/teacher.py) remains the source of truth and validates every result.
const RESULT_BASED_TITLES = ['IELTS', 'IGCSE', 'IAL', 'Qudurat', 'Tahsili'];
const IGCSE_GRADE_OPTIONS = ['A*', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'U'];
const IAL_GRADE_OPTIONS = ['A*', 'A', 'B', 'C', 'D', 'E', 'U'];
const ATTEMPT_LIMITS = { Qudurat: 5, Tahsili: 2 };
const AWARD_LEVELS = ['Pass', 'Merit', 'Distinction'];

// result_value comes back as a number-string (score titles) or a
// JSON-encoded array string (grade titles). Render either readably.
function formatResultValue(rv) {
  if (rv === null || rv === undefined) return '';
  try {
    const parsed = JSON.parse(rv);
    if (Array.isArray(parsed)) return parsed.join(', ');
  } catch (e) {
    // not JSON — fall through and show the raw value (a score string)
  }
  return String(rv);
}

// One row in the Academic Results editor. Holds its own input state so the
// parent dashboard's state stays minimal; calls teacher.recordObjectiveResult
// on save and reports success/error inline. Recording a result does not
// change the objective's approval status (that flows through reviews).
function ResultEntryRow({ studentId, objective }) {
  const title = objective.title;
  const isGradeBased = title === 'IGCSE' || title === 'IAL';
  const hasAttempts = title === 'Qudurat' || title === 'Tahsili';
  const maxAttempts = ATTEMPT_LIMITS[title] || 1;
  const allowedGrades = title === 'IGCSE' ? IGCSE_GRADE_OPTIONS : IAL_GRADE_OPTIONS;
  const scoreMax = title === 'IELTS' ? 9 : 100;
  const scoreStep = title === 'IELTS' ? 0.5 : 1;

  const [score, setScore] = useState('');
  const [gradesInput, setGradesInput] = useState('');
  const [attempts, setAttempts] = useState(1);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [savedMsg, setSavedMsg] = useState('');

  const handleSave = async () => {
    setError('');
    setSavedMsg('');

    const payload = { studentId: Number(studentId), objectiveId: objective.objective_id };

    if (isGradeBased) {
      const grades = gradesInput
        .split(',')
        .map((g) => g.trim().toUpperCase())
        .filter(Boolean);
      if (grades.length === 0) {
        setError('Enter at least one grade (comma-separated).');
        return;
      }
      const bad = grades.filter((g) => !allowedGrades.includes(g));
      if (bad.length > 0) {
        setError(`Invalid ${title} grade(s): ${bad.join(', ')}`);
        return;
      }
      payload.grades = grades;
    } else {
      if (score === '' || Number.isNaN(Number(score))) {
        setError('Enter a numeric score.');
        return;
      }
      const numeric = Number(score);
      if (numeric < 0 || numeric > scoreMax) {
        setError(`${title} score must be between 0 and ${scoreMax}.`);
        return;
      }
      payload.score = numeric;
      if (hasAttempts) payload.attempts = Number(attempts);
    }

    setSaving(true);
    try {
      const res = await teacher.recordObjectiveResult(payload);
      const rv = res?.data?.result_value;
      setSavedMsg(`Saved${rv ? `: ${formatResultValue(rv)}` : ''} \u2713`);
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not save result.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        flexWrap: 'wrap',
        padding: '12px 14px',
        borderRadius: 12,
        background: 'rgba(255,255,255,0.85)',
        border: '1px solid rgba(0,0,0,0.06)',
      }}
    >
      <div style={{ minWidth: 92, fontWeight: 800, color: '#0b3f33' }}>{title}</div>

      {isGradeBased ? (
        <input
          type="text"
          value={gradesInput}
          onChange={(e) => setGradesInput(e.target.value)}
          placeholder={`e.g. ${allowedGrades.slice(0, 3).join(', ')}`}
          disabled={saving}
          style={{ flex: '1 1 200px', minWidth: 160 }}
        />
      ) : (
        <input
          type="number"
          value={score}
          onChange={(e) => setScore(e.target.value)}
          min={0}
          max={scoreMax}
          step={scoreStep}
          placeholder={`0–${scoreMax}`}
          disabled={saving}
          style={{ width: 110 }}
        />
      )}

      {hasAttempts && (
        <label style={{ fontSize: 13, color: '#4e615d', display: 'flex', alignItems: 'center', gap: 6 }}>
          Attempt
          <select
            value={attempts}
            onChange={(e) => setAttempts(Number(e.target.value))}
            disabled={saving}
          >
            {Array.from({ length: maxAttempts }, (_, i) => i + 1).map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
      )}

      <button
        type="button"
        className="btn-review"
        onClick={handleSave}
        disabled={saving}
      >
        {saving ? 'Saving…' : 'Save result'}
      </button>

      {savedMsg && <span style={{ color: '#02664b', fontWeight: 700, fontSize: 13 }}>{savedMsg}</span>}
      {error && <span style={{ color: '#c0392b', fontWeight: 600, fontSize: 13 }}>{error}</span>}

      {isGradeBased && (
        <div style={{ flexBasis: '100%', fontSize: 12, color: '#7f8c8d' }}>
          Allowed: {allowedGrades.join(', ')} — comma-separated, one per subject.
        </div>
      )}
    </div>
  );
}

// Academic Results editor: pulls the result-based objectives out of the
// student's report (Academic quadrant) and renders one ResultEntryRow each.
// Renders nothing if the report has no result-based objectives.
function AcademicResultsBlock({ studentId, report }) {
  const academic = (report.quadrant_reports || []).find(
    (q) => q.quadrant_name === 'Academic'
  );
  const objectives = (academic?.objectives || []).filter((o) =>
    RESULT_BASED_TITLES.includes(o.title)
  );
  if (objectives.length === 0) return null;

  return (
    <div style={{ marginTop: 28 }}>
      <h4 style={{ margin: 0 }}>Academic Results</h4>
      <p style={{ fontSize: 13, color: '#6d7f7a', margin: '6px 0 14px' }}>
        Record exam outcomes for result-based objectives. This stores the
        result for the skills profile and does not change the objective's
        approval status.
      </p>
      <div style={{ display: 'grid', gap: 10 }}>
        {objectives.map((o) => (
          <ResultEntryRow key={o.objective_id} studentId={studentId} objective={o} />
        ))}
      </div>
    </div>
  );
}

// Formal Diploma panel: shows live eligibility for the selected student and,
// when eligible, lets the teacher record the Pass/Merit/Distinction band.
// The system never computes the band; it records the teacher's selection.
// Keyed by studentId in the parent so it re-fetches on student change.
function DiplomaAwardPanel({ studentId }) {
  const [state, setState] = useState(null); // { eligible_for_diploma, award, student_name }
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [level, setLevel] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setLoadError('');
    teacher
      .getDiplomaAward(studentId)
      .then((res) => {
        if (!alive) return;
        setState(res.data);
        setLevel(res.data?.award?.award_level || '');
        setNotes(res.data?.award?.notes || '');
      })
      .catch((err) => {
        if (!alive) return;
        setLoadError(extractErrorMessage(err, 'Could not load diploma status.'));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [studentId]);

  const refetch = () => {
    teacher
      .getDiplomaAward(studentId)
      .then((res) => setState(res.data))
      .catch(() => {});
  };

  const handleRecord = async () => {
    setSaveError('');
    if (!level) {
      setSaveError('Choose an award level.');
      return;
    }
    setSaving(true);
    try {
      await teacher.setDiplomaAward({
        studentId: Number(studentId),
        awardLevel: level,
        notes: notes.trim() || null,
      });
      refetch();
    } catch (err) {
      setSaveError(extractErrorMessage(err, 'Could not record award.'));
    } finally {
      setSaving(false);
    }
  };

  const eligible = !!state?.eligible_for_diploma;
  const award = state?.award || null;

  return (
    <div
      style={{
        marginTop: 28,
        padding: 18,
        borderRadius: 14,
        background: 'rgba(2, 102, 75, 0.06)',
        border: '1px solid rgba(2, 102, 75, 0.12)',
      }}
    >
      <h4 style={{ margin: 0 }}>Formal Diploma</h4>

      {loading && <div style={{ marginTop: 10, color: '#6d7f7a' }}>Loading diploma status…</div>}

      {loadError && (
        <div className="error-message" style={{ marginTop: 10 }}>
          {loadError}
        </div>
      )}

      {!loading && !loadError && (
        <>
          <div
            style={{
              marginTop: 10,
              fontWeight: 700,
              color: eligible ? '#02664b' : '#8a6d3b',
            }}
          >
            {eligible
              ? 'Eligible — all mandatory objectives approved.'
              : 'Not yet eligible — all mandatory objectives must be approved.'}
          </div>

          {award && (
            <div
              style={{
                marginTop: 12,
                padding: '10px 14px',
                borderRadius: 10,
                background: 'rgba(243, 156, 18, 0.12)',
                border: '1px solid rgba(243, 156, 18, 0.25)',
                color: '#0b3f33',
                fontWeight: 700,
              }}
            >
              Awarded: {award.award_level}
              {award.selected_at && (
                <span style={{ fontWeight: 500, color: '#4e615d' }}>
                  {' '}· {new Date(award.selected_at).toLocaleDateString()}
                </span>
              )}
              {award.selected_by_name && (
                <span style={{ fontWeight: 500, color: '#4e615d' }}>
                  {' '}· by {award.selected_by_name}
                </span>
              )}
            </div>
          )}

          <div style={{ marginTop: 16, opacity: eligible ? 1 : 0.55 }}>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              {AWARD_LEVELS.map((lvl) => (
                <button
                  key={lvl}
                  type="button"
                  onClick={() => setLevel(lvl)}
                  disabled={!eligible || saving}
                  style={{
                    padding: '10px 16px',
                    borderRadius: 10,
                    minHeight: 44,
                    fontWeight: 700,
                    cursor: eligible ? 'pointer' : 'not-allowed',
                    color: level === lvl ? '#ffffff' : '#0b3f33',
                    background: level === lvl ? '#02664b' : 'rgba(255,255,255,0.85)',
                    border: '1px solid rgba(2, 102, 75, 0.25)',
                  }}
                >
                  {lvl}
                </button>
              ))}
            </div>

            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Notes (optional)"
              disabled={!eligible || saving}
              style={{ marginTop: 12, width: '100%', minHeight: 64 }}
            />

            {saveError && (
              <div className="error-message" style={{ marginTop: 10 }}>
                {saveError}
              </div>
            )}

            <button
              type="button"
              className="btn-login"
              onClick={handleRecord}
              disabled={!eligible || saving}
              style={{ marginTop: 12 }}
            >
              {saving ? 'Recording…' : award ? 'Update award' : 'Record award'}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// One card in the Misk Core activity review queue (Chunk 32). Holds its own
// feedback + busy state and calls teacher.reviewActivity on a decision; the
// parent reloads the queue via onReviewed. Approving/rejecting is allowed
// from any current status so a teacher can correct a prior decision.
function ActivityReviewCard({ activity, onReviewed }) {
  const [feedback, setFeedback] = useState(activity.review_feedback || '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const decide = async (decision) => {
    setError('');
    setBusy(true);
    try {
      await teacher.reviewActivity({
        activityId: activity.id,
        decision,
        feedback: feedback.trim() || null,
      });
      onReviewed();
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not submit the decision.'));
      setBusy(false);
    }
  };

  return (
    <div className="queue-item">
      <div className="queue-info">
        <h4>{activity.student_name}</h4>
        <p>
          {activity.category_name} • {activity.title}{' '}
          <span className={`status-badge status-${activity.status}`}>
            {activity.status.replace('_', ' ')}
          </span>
        </p>
        {activity.activity_date && (
          <p style={{ fontSize: 13, color: '#6d7f7a' }}>
            {new Date(activity.activity_date).toLocaleDateString()}
          </p>
        )}
        {activity.description && <p>{activity.description}</p>}
        {activity.tags && activity.tags.length > 0 && (
          <p style={{ fontSize: 13, color: '#6d7f7a' }}>
            Tags: {activity.tags.join(', ')}
          </p>
        )}
        {activity.stored_filename && (
          <AttachmentLink
            storedFilename={activity.stored_filename}
            originalFilename={activity.original_filename}
          />
        )}
      </div>

      <div className="queue-actions" style={{ marginTop: 12 }}>
        <textarea
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          placeholder="Feedback (optional)"
          disabled={busy}
          style={{ width: '100%', minHeight: 56 }}
        />
        {error && <div className="error-message" style={{ marginTop: 8 }}>{error}</div>}
        <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
          <button
            type="button"
            className="btn-approve"
            disabled={busy}
            onClick={() => decide('approved')}
          >
            {busy ? '…' : 'Approve'}
          </button>
          <button
            type="button"
            className="btn-reject"
            disabled={busy}
            onClick={() => decide('rejected')}
          >
            {busy ? '…' : 'Reject'}
          </button>
        </div>
      </div>
    </div>
  );
}

// Skills profile panel for the Student Reports tab (Chunk 33). Fetches the
// student's computed 16-dimension profile and renders the two radars. Keyed by
// studentId in the parent so it re-fetches on student change. Read-only.
function SkillsProfilePanel({ studentId }) {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError('');
    teacher
      .getSkillsProfile(studentId)
      .then((res) => { if (alive) setProfile(res.data); })
      .catch((err) => { if (alive) setError(extractErrorMessage(err, 'Could not load the skills profile.')); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [studentId]);

  return (
    <div style={{ marginTop: 28 }}>
      <h4 style={{ margin: 0 }}>Misk Skills Profile</h4>
      {loading && <div style={{ marginTop: 8, color: '#6d7f7a' }}>Loading…</div>}
      {error && <div className="error-message" style={{ marginTop: 8 }}>{error}</div>}
      {profile && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 24, marginTop: 12 }}>
          <SkillsRadar title="How I Think" accent="#02664b" data={profile.dimensions.filter((d) => d.group === 'ACP')} />
          <SkillsRadar title="Who I Am" accent="#0fb989" data={profile.dimensions.filter((d) => d.group === 'VAA')} />
        </div>
      )}
    </div>
  );
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

  // Chunk 32: Misk Core activity review queue.
  const [activityQueue, setActivityQueue] = useState([]);
  const [activityFilter, setActivityFilter] = useState('pending_review');
  const [activityLoading, setActivityLoading] = useState(false);
  const [activityError, setActivityError] = useState('');

  const user = getUser();

  useEffect(() => {
    loadSubmissions();
    loadStudents();
  }, [filter]);

  // Chunk 32: load the activity queue when its tab is active or the status
  // filter changes. Gated on activeTab so we don't fetch it needlessly.
  useEffect(() => {
    if (activeTab === 'activities') {
      loadActivityQueue(activityFilter);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, activityFilter]);

  const loadActivityQueue = async (status) => {
    setActivityLoading(true);
    setActivityError('');
    try {
      const response = await teacher.getActivitiesForReview(status);
      setActivityQueue(response.data.activities);
    } catch (err) {
      setActivityError(extractErrorMessage(err, 'Could not load the activity queue.'));
    } finally {
      setActivityLoading(false);
    }
  };

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

          <button
            className={`tab ${activeTab === 'activities' ? 'active' : ''}`}
            onClick={() => setActiveTab('activities')}
            style={{ ...tabBase, ...(activeTab === 'activities' ? tabActive : tabInactive) }}
          >
            Activity Review
            {activeTab === 'activities' && <span style={activeUnderline} />}
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

                <AcademicResultsBlock studentId={selectedStudent} report={studentReport} />
                <DiplomaAwardPanel key={selectedStudent} studentId={selectedStudent} />
                <SkillsProfilePanel key={`skills-${selectedStudent}`} studentId={selectedStudent} />
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

        {activeTab === 'activities' && (
          <>
            <div className="filter-bar">
              <select
                value={activityFilter}
                onChange={(e) => setActivityFilter(e.target.value)}
              >
                <option value="pending_review">Pending Review</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
                <option value="all">All</option>
              </select>
            </div>

            <div className="card">
              <h3>Misk Core Activity Queue ({activityQueue.length})</h3>
              {activityError && <div className="error-message">{activityError}</div>}
              {activityLoading ? (
                <div style={{ color: '#6d7f7a' }}>Loading…</div>
              ) : (
                <div className="review-queue">
                  {activityQueue.length === 0 && (
                    <div style={{ color: '#6d7f7a' }}>No activities in this view.</div>
                  )}
                  {activityQueue.map((a) => (
                    <ActivityReviewCard
                      key={a.id}
                      activity={a}
                      onReviewed={() => loadActivityQueue(activityFilter)}
                    />
                  ))}
                </div>
              )}
            </div>
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