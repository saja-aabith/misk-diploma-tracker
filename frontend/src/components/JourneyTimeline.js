import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { student } from '../api/client';
import './JourneyTimeline.css';

/**
 * JourneyTimeline — Year 7→12 horizontal strip on the student dashboard.
 *
 * Renders 6 year-nodes from a /student/journey payload. Each year may
 * carry milestone "flags" coloured by quadrant. The current year is
 * emphasised with a soft MISK-green glow ring; future years are muted
 * dashed outlines.
 *
 * Animation choreography on mount (post-data-load):
 *   1. Track fill animates left-to-right to current-year position (~800ms)
 *   2. Flags fade in with stagger after the track reaches each year
 *
 * If the student has no current_year set (e.g. non-hero seeded students),
 * the component still renders cleanly: all 6 nodes show as muted outlines
 * with a "Year not yet set" subtitle and no flags.
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

  // Track fill width: extends from the leftmost node (Year 7) to the
  // centre of the current-year node. Six nodes span 5 segments, so the
  // current year's centre sits at ((current - 7) / 5) * 100 %.
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
            ? `Currently in Year ${journey.current_year} · ${totalMilestones} milestone${totalMilestones === 1 ? '' : 's'} earned`
            : 'Year not yet set'}
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
          <Flag
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

      <div className="journey-node-label">Year {year}</div>
    </div>
  );
}

function Flag({ milestone, animated, delayMs, onHover }) {
  return (
    <div
      className="journey-flag"
      style={{
        '--flag-color': milestone.quadrant_color,
        opacity: animated ? 1 : 0,
        transform: animated ? 'translateY(0)' : 'translateY(6px)',
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
      <span className="journey-flag-pole" aria-hidden="true" />
      <span className="journey-flag-body" aria-hidden="true" />
    </div>
  );
}

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