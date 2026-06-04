import React, { useState, useEffect, useMemo } from 'react';
import { student } from '../api/client';
import './DiplomaIdentityPanel.css';

/**
 * DiplomaIdentityPanel — sits beside the QuadrantCircle3D on the
 * student dashboard. Calm institutional card: large gradient
 * avatar with initials, student name, current-grade pill, divider,
 * "MISK Diploma" / "Class of YYYY" cohort lines.
 *
 * Data sources:
 *   - studentName / overallCompletion: passed from parent
 *     (StudentDashboard already has these in dashboardData)
 *   - currentGrade: self-fetched from /student/journey, which
 *     returns `current_year` (= grade). The journey endpoint is
 *     already called by JourneyTimeline elsewhere on the page;
 *     calling it twice is a deliberate scope trade-off (see the
 *     decision log in the chunk that introduced this component)
 *     rather than refactoring shared state ahead of the demo.
 *
 * Graceful states:
 *   - Pre-load: avatar shows '…', no grade pill, no cohort line
 *   - currentGrade is null (non-hero students): grade pill and
 *     cohort line both hidden; the panel still renders with name
 *     and "MISK Diploma" so it doesn't feel broken.
 */
function DiplomaIdentityPanel({ studentName, overallCompletion }) {
  const [currentGrade, setCurrentGrade] = useState(null);
  const [journeyLoaded, setJourneyLoaded] = useState(false);

  useEffect(() => {
    let alive = true;
    student
      .getJourney()
      .then((response) => {
        if (!alive) return;
        setCurrentGrade(response.data?.current_year ?? null);
        setJourneyLoaded(true);
      })
      .catch((err) => {
        console.error('DiplomaIdentityPanel: failed to load journey', err);
        if (alive) setJourneyLoaded(true);
      });
    return () => {
      alive = false;
    };
  }, []);

  const initials = useMemo(() => getInitials(studentName), [studentName]);
  const cohortLabel = useMemo(
    () => computeGraduationLabel(currentGrade),
    [currentGrade]
  );

  return (
    <aside className="diploma-identity-panel" aria-label="Student identity">
      <div className="diploma-identity-avatar" aria-hidden="true">
        <span className="diploma-identity-avatar-initials">{initials}</span>
      </div>

      <div className="diploma-identity-name">
        {studentName || 'Loading…'}
      </div>

      {journeyLoaded && currentGrade != null && (
        <div className="diploma-identity-grade-pill">
          Grade {currentGrade}
        </div>
      )}

      <div className="diploma-identity-divider" aria-hidden="true" />

      <div className="diploma-identity-meta">
        <div className="diploma-identity-school">MISK Diploma</div>
        {cohortLabel && (
          <div className="diploma-identity-cohort">{cohortLabel}</div>
        )}
      </div>

      {typeof overallCompletion === 'number' && (
        <div className="diploma-identity-completion">
          <div className="diploma-identity-completion-label">
            Overall Progress
          </div>
          <div className="diploma-identity-completion-value">
            {overallCompletion.toFixed(1)}%
          </div>
        </div>
      )}
    </aside>
  );
}

// ----- helpers (module scope, pure, easy to unit-test) -----

/**
 * Return up to 2 uppercase initials from a full name.
 *   "Sara Al-Ghamdi"     -> "SA"
 *   "Abdullah Al-Otaibi" -> "AA"
 *   "Mohammed"           -> "M"
 *   undefined / ""       -> "…"
 *
 * Splits on whitespace; the hyphen in Saudi family names is part
 * of the surname unit so it's preserved as a single token.
 */
function getInitials(name) {
  if (!name || typeof name !== 'string') return '…';
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '…';
  if (parts.length === 1) return parts[0][0].toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/**
 * Compute "Class of YYYY" from current grade.
 *
 * Saudi academic calendar runs Sep -> Jun, so Grade 12 students
 * in mid-year graduate later that same calendar year. The simple
 * formula `currentCalendarYear + (12 - grade)` reads correctly
 * for the hero set throughout the year:
 *   Grade 7  -> Class of (now + 5)
 *   Grade 12 -> Class of (now + 0)
 *
 * Returns null for unset / out-of-range grades so the parent can
 * conditionally hide the line.
 */
function computeGraduationLabel(grade) {
  if (typeof grade !== 'number') return null;
  if (grade < 7 || grade > 12) return null;
  const now = new Date().getFullYear();
  return `Class of ${now + (12 - grade)}`;
}

export default DiplomaIdentityPanel;