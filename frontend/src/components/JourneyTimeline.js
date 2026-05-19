import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  BookOpenCheck,
  BriefcaseBusiness,
  Landmark,
  Mountain,
  Sparkles,
  Flag as FlagIcon,
} from 'lucide-react';
import { student } from '../api/client';
import './JourneyTimeline.css';

/**
 * JourneyTimeline — Grade 7→12 horizontal strip on the student dashboard.
 *
 * Renders 6 grade-nodes from a /student/journey payload. Each grade may
 * carry milestone pennant "flags" coloured by quadrant. The current grade
 * is emphasised with a soft MISK-green glow ring; future grades are muted
 * dashed outlines.
 *
 * Animation choreography on mount (post-data-load):
 *   1. Track fill animates left-to-right to the current-grade position (~900ms)
 *   2. Pennant flags fade-in with stagger, then sway gently in a loop
 *
 * IMPORTANT NAMING NOTE:
 *   This component refers to school stage as "Grade" in all user-visible
 *   strings (e.g. "Grade 9", "Grade not yet set"). The underlying backend
 *   names — `student_year` on the users table, `year` in the
 *   /student/journey JSON payload — remain unchanged so we don't break
 *   the API contract or DB schema. The relabel is purely presentational.
 */
function JourneyTimeline() {
  const [journey, setJourney] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [animated, setAnimated] = useState(false);
  const [hoveredFlag, setHoveredFlag] = useState(null);

  useEffect(() => {
    let alive = true;
    student
      .getJourney()
      .then((response) => {
        if (!alive) return;
        setJourney(response.data);
        setLoading(false);
        // Double-rAF: ensure the initial DOM (animated=false state) has
        // painted before we flip to animated=true, so CSS transitions
        // actually run on the change rather than being skipped.
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            if (alive) setAnimated(true);
          });
        });
      })
      .catch((err) => {
        if (!alive) return;
        console.error('Failed to load journey:', err);
        setError('Failed to load journey');
        setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  // Track fill width: extends from the leftmost node (Grade 7) to the
  // centre of the current-grade node. Six nodes span 5 segments, so the
  // current grade's centre sits at ((current - 7) / 5) * 100 %.
  // When current_year is null we want a 0-width fill.
  const trackFillPct = useMemo(() => {
    if (!journey || journey.current_year == null) return 0;
    const pos = journey.current_year - 7;
    return Math.max(0, Math.min(100, (pos / 5) * 100));
  }, [journey]);

  const totalMilestones = useMemo(() => {
    if (!journey) return 0;
    return journey.years.reduce((acc, y) => acc + y.milestones.length, 0);
  }, [journey]);

  const handleFlagHover = useCallback((flag) => setHoveredFlag(flag), []);

  if (loading) {
    return (
      <div className="card journey-card">
        <div className="journey-loading">Loading your MISK journey…</div>
      </div>
    );
  }

  if (error || !journey) {
    // Silent-ish failure: the rest of the dashboard still works. We
    // surface the message but don't disrupt the page.
    return (
      <div className="card journey-card">
        <div className="journey-loading">{error || 'No journey data available.'}</div>
      </div>
    );
  }

  return (
    <div className="card journey-card">
      <div className="journey-header">
        <h3>Your MISK Journey</h3>
        <p className="journey-subtitle">
          {journey.current_year
            ? `Currently in Grade ${journey.current_year} · ${totalMilestones} milestone${totalMilestones === 1 ? '' : 's'} earned`
            : 'Grade not yet set'}
        </p>
      </div>

      <div className="journey-track-wrapper">
        <div className="journey-track">
          <div
            className="journey-track-fill"
            style={{ width: animated ? `${trackFillPct}%` : '0%' }}
          />
        </div>

        <div className="journey-nodes">
          {journey.years.map((y, idx) => (
            <JourneyNode
              key={y.year}
              yearData={y}
              animated={animated}
              flagDelayBaseMs={500 + idx * 120}
              onFlagHover={handleFlagHover}
            />
          ))}
        </div>

        {hoveredFlag && (
          <div className="journey-flag-tooltip">
            <div
              className="journey-flag-tooltip-dot"
              style={{ background: hoveredFlag.quadrant_color }}
            />
            <div>
              <div className="journey-flag-tooltip-title">{hoveredFlag.title}</div>
              <div className="journey-flag-tooltip-meta">
                {hoveredFlag.quadrant_name} · {formatMilestoneDate(hoveredFlag.date)}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function JourneyNode({ yearData, animated, flagDelayBaseMs, onFlagHover }) {
  const { year, status, milestones } = yearData;

  return (
    <div className={`journey-node journey-node--${status}`}>
      <div className="journey-flags">
        {milestones.map((m, idx) => (
          <Pennant
            key={m.id}
            milestone={m}
            animated={animated}
            delayMs={flagDelayBaseMs + idx * 90}
            onHover={onFlagHover}
          />
        ))}
      </div>

      <div className="journey-node-dot">
        {status === 'current' && <span className="journey-node-glow" aria-hidden="true" />}
      </div>

      <div className="journey-node-label">Grade {year}</div>
    </div>
  );
}

/**
 * Pennant — triangular flag marker with quadrant icon and ambient
 * sway/pulse-glow animations.
 *
 * Visual structure:
 *   - .journey-pennant-pole     — thin vertical line, the "flagpole"
 *   - .journey-pennant-flag     — clip-pathed triangle, quadrant colour
 *   - .journey-pennant-icon     — quadrant Lucide icon, white on colour
 *
 * The sway animation rotates the .journey-pennant-stem (pole + flag
 * together) around the bottom of the pole so the pennant tip arcs
 * naturally, like a flag fluttering in light wind. Pulse glow is on the
 * triangle itself, breathing the box-shadow. Both pause on hover/focus
 * so the user can read the flag and trigger the tooltip without the
 * marker drifting under the cursor.
 */
function Pennant({ milestone, animated, delayMs, onHover }) {
  const Icon = QUADRANT_ICON_MAP[milestone.quadrant_name] || FlagIcon;

  return (
    <div
      className="journey-flag"
      style={{
        '--flag-color': milestone.quadrant_color,
        opacity: animated ? 1 : 0,
        transform: animated ? 'translateY(0)' : 'translateY(8px)',
        transition: `opacity 320ms ease-out ${delayMs}ms, transform 320ms ease-out ${delayMs}ms`,
      }}
      onMouseEnter={() => onHover(milestone)}
      onMouseLeave={() => onHover(null)}
      tabIndex={0}
      onFocus={() => onHover(milestone)}
      onBlur={() => onHover(null)}
      role="button"
      aria-label={`${milestone.title}, ${milestone.quadrant_name}`}
    >
      <span className="journey-pennant-stem" aria-hidden="true">
        <span className="journey-pennant-pole" />
        <span className="journey-pennant-flag">
          <span className="journey-pennant-icon">
            <Icon size={14} strokeWidth={2.5} color="#ffffff" />
          </span>
        </span>
      </span>
    </div>
  );
}

// Quadrant name -> Lucide icon component. Keyed by the exact strings
// returned by the backend (`JourneyMilestone.quadrant_name`), which
// match `quadrants.name`. If an unknown name appears we fall back to a
// generic Flag icon at the call site so the UI degrades cleanly.
const QUADRANT_ICON_MAP = {
  Academic: BookOpenCheck,
  Internship: BriefcaseBusiness,
  'National Identity': Landmark,
  Leadership: Mountain,
  'Misk Core': Sparkles,
};

function formatMilestoneDate(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
    });
  } catch {
    return iso;
  }
}

export default JourneyTimeline;