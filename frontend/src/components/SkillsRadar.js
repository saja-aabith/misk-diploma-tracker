import React from 'react';

/**
 * SkillsRadar — a calm, dependency-free SVG radar for one group of skills
 * dimensions (0–100). Used by both the student and teacher skills views so the
 * two render identically. Pure presentational: it takes already-computed scores
 * from GET /…/skills-profile and draws them; it does no fetching or maths.
 *
 * Props:
 *   title   — heading above the radar (e.g. "How I Think")
 *   data    — array of { dimension, score, status } (the group's dimensions)
 *   accent  — hex colour for the data polygon / points (defaults to MISK green)
 *   size    — SVG square size in px (default 320)
 *
 * Dimensions with status 'no_evidence' (score 0) still draw their axis + label
 * so the gaps are visible and honest; they're shown muted in the value list.
 */
function SkillsRadar({ title, data, accent = '#02664b', size = 320 }) {
  const items = Array.isArray(data) ? data : [];
  const n = items.length;
  const cx = size / 2;
  const cy = size / 2;
  const R = size * 0.32;
  const levels = [0.25, 0.5, 0.75, 1];

  // Angle for axis i, starting at the top (−90°) and going clockwise.
  const angleFor = (i) => (-90 + (i * 360) / n) * (Math.PI / 180);

  const pointAt = (i, radius) => {
    const a = angleFor(i);
    return [cx + Math.cos(a) * radius, cy + Math.sin(a) * radius];
  };

  const gridPolygon = (level) =>
    items
      .map((_, i) => {
        const [x, y] = pointAt(i, R * level);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' ');

  const dataPolygon = items
    .map((d, i) => {
      const v = Math.max(0, Math.min(100, Number(d.score) || 0));
      const [x, y] = pointAt(i, R * (v / 100));
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  const labelFor = (i) => {
    const a = angleFor(i);
    const [x, y] = pointAt(i, R + 14);
    const cos = Math.cos(a);
    const sin = Math.sin(a);
    let anchor = 'middle';
    if (cos > 0.25) anchor = 'start';
    else if (cos < -0.25) anchor = 'end';
    const dy = sin > 0.5 ? 10 : sin < -0.5 ? -4 : 4;
    return { x, y: y + dy, anchor };
  };

  return (
    <div style={{ flex: '1 1 300px', minWidth: 280 }}>
      <h4 style={{ color: '#02664b', margin: '0 0 8px', textAlign: 'center' }}>{title}</h4>

      <svg
        viewBox={`0 0 ${size} ${size}`}
        width="100%"
        role="img"
        aria-label={`${title} skills radar`}
        style={{ display: 'block', margin: '0 auto', maxWidth: size }}
      >
        {levels.map((lv) => (
          <polygon
            key={lv}
            points={gridPolygon(lv)}
            fill="none"
            stroke="rgba(2,102,75,0.12)"
            strokeWidth="1"
          />
        ))}

        {items.map((_, i) => {
          const [x, y] = pointAt(i, R);
          return (
            <line
              key={`axis-${i}`}
              x1={cx}
              y1={cy}
              x2={x}
              y2={y}
              stroke="rgba(2,102,75,0.12)"
              strokeWidth="1"
            />
          );
        })}

        <polygon points={dataPolygon} fill={accent} fillOpacity="0.22" stroke={accent} strokeWidth="2" />

        {items.map((d, i) => {
          const v = Math.max(0, Math.min(100, Number(d.score) || 0));
          const [x, y] = pointAt(i, R * (v / 100));
          return (
            <circle key={`pt-${i}`} cx={x} cy={y} r="3" fill={accent}>
              <title>{`${d.dimension}: ${v}`}</title>
            </circle>
          );
        })}

        {items.map((d, i) => {
          const { x, y, anchor } = labelFor(i);
          const muted = d.status === 'no_evidence';
          return (
            <text
              key={`lbl-${i}`}
              x={x}
              y={y}
              textAnchor={anchor}
              fontSize="10"
              fill={muted ? '#aab2ae' : '#3d5650'}
            >
              {d.dimension}
            </text>
          );
        })}
      </svg>

      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '6px 14px',
          justifyContent: 'center',
          marginTop: 10,
        }}
      >
        {items.map((d) => {
          const muted = d.status === 'no_evidence';
          return (
            <span key={d.dimension} style={{ fontSize: 12, color: muted ? '#aab2ae' : '#445' }}>
              {d.dimension}{' '}
              <strong style={{ color: muted ? '#aab2ae' : '#02664b' }}>
                {muted ? '—' : d.score}
              </strong>
            </span>
          );
        })}
      </div>
    </div>
  );
}

export default SkillsRadar;
