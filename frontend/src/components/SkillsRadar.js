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
 *   size    — radar diameter area in px (default 300); the viewBox adds margin
 *             around it for labels, so the rendered SVG is wider/taller.
 *
 * Dimensions with status 'no_evidence' (score 0) still draw their axis + label
 * so the gaps are visible and honest; they're shown muted in the value list.
 */

// Split a dimension name onto at most two balanced lines so long labels
// ("Concerned for Society", "Creative & Enterprising") don't overflow. Single
// words and short names stay on one line.
function wrapLabel(name) {
  if (name.length <= 14 || name.indexOf(' ') === -1) return [name];
  const words = name.split(' ');
  let best = null;
  for (let i = 1; i < words.length; i++) {
    const a = words.slice(0, i).join(' ');
    const b = words.slice(i).join(' ');
    const score = Math.max(a.length, b.length);
    if (best === null || score < best.score) best = { a, b, score };
  }
  return [best.a, best.b];
}

function SkillsRadar({ title, data, accent = '#02664b', size = 300, showValues = true }) {
  const items = Array.isArray(data) ? data : [];
  const n = items.length;

  const marginX = 92;
  const marginTop = 30;
  const marginBottom = 30;
  const W = size + marginX * 2;
  const H = size + marginTop + marginBottom;
  const cx = marginX + size / 2;
  const cy = marginTop + size / 2;
  const R = size * 0.32;
  const levels = [0.25, 0.5, 0.75, 1];

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

  return (
    <div style={{ flex: '1 1 320px', minWidth: 300 }}>
      <h4 style={{ color: '#02664b', margin: '0 0 8px', textAlign: 'center' }}>{title}</h4>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        role="img"
        aria-label={`${title} skills radar`}
        style={{ display: 'block', margin: '0 auto', maxWidth: W, overflow: 'visible' }}
      >
        {levels.map((lv) => (
          <polygon key={lv} points={gridPolygon(lv)} fill="none" stroke="rgba(2,102,75,0.12)" strokeWidth="1" />
        ))}

        {items.map((_, i) => {
          const [x, y] = pointAt(i, R);
          return <line key={`axis-${i}`} x1={cx} y1={cy} x2={x} y2={y} stroke="rgba(2,102,75,0.12)" strokeWidth="1" />;
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
          const a = angleFor(i);
          const cos = Math.cos(a);
          const sin = Math.sin(a);
          const [lx, ly] = pointAt(i, R + 14);
          let anchor = 'middle';
          if (cos > 0.25) anchor = 'start';
          else if (cos < -0.25) anchor = 'end';
          const lines = wrapLabel(d.dimension);
          const nudge = sin < -0.4 ? -3 : sin > 0.4 ? 3 : 0;
          const startY = ly - (lines.length - 1) * 5.5 + nudge;
          const muted = d.status === 'no_evidence';
          return (
            <text key={`lbl-${i}`} x={lx} y={startY} textAnchor={anchor} fontSize="10" fill={muted ? '#aab2ae' : '#3d5650'}>
              {lines.map((ln, k) => (
                <tspan key={k} x={lx} dy={k === 0 ? 0 : 11}>{ln}</tspan>
              ))}
            </text>
          );
        })}
      </svg>

      {showValues && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 14px', justifyContent: 'center', marginTop: 10 }}>
          {items.map((d) => {
            const muted = d.status === 'no_evidence';
            return (
              <span key={d.dimension} style={{ fontSize: 12, color: muted ? '#aab2ae' : '#445' }}>
                {d.dimension}{' '}
                <strong style={{ color: muted ? '#aab2ae' : '#02664b' }}>{muted ? '—' : d.score}</strong>
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default SkillsRadar;