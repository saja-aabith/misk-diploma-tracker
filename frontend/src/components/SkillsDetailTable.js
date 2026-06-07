import React from 'react';

/**
 * SkillsDetailTable — a calm, grouped table of skills dimensions with their
 * 0–100 scores. Used twice on the skills views: once for the 20 ACP leaf
 * characteristics (grouped by their 5 HPL groups) and once for the 11 VAA
 * dimensions (grouped by their HPL clusters), so both halves read identically.
 *
 * Pure presentational: it takes already-computed rows from the skills-profile
 * payload — each row is { dimension, category, score, status } — and lays them
 * out grouped by `category`. It does no fetching or maths. Rows whose status is
 * 'no_evidence' show "—" in muted grey. Colours match the rest of the skills UI.
 *
 * Props:
 *   title      — heading above the table (e.g. "How I Think — detail")
 *   rows       — array of { dimension, category, score, status }
 *   groupLabel — header for the grouping column (default "Group")
 *   itemLabel  — header for the dimension column (default "Characteristic")
 */
function SkillsDetailTable({ title, rows, groupLabel = 'Group', itemLabel = 'Characteristic' }) {
  const items = Array.isArray(rows) ? rows : [];
  if (items.length === 0) return null;

  // Preserve the payload's category order.
  const order = [];
  const byCategory = {};
  items.forEach((row) => {
    const cat = row.category || 'Other';
    if (!byCategory[cat]) {
      byCategory[cat] = [];
      order.push(cat);
    }
    byCategory[cat].push(row);
  });

  const cell = {
    padding: '8px 16px',
    borderBottom: '1px solid #eef2f0',
    fontSize: 13,
    verticalAlign: 'top',
  };
  const headCell = {
    padding: '8px 16px',
    borderBottom: '2px solid #d7e3de',
    fontSize: 12,
    fontWeight: 700,
    color: '#02664b',
    textAlign: 'left',
  };

  return (
    <div style={{ width: '100%', marginTop: 20 }}>
      <h4 style={{ color: '#02664b', margin: '0 0 12px' }}>{title}</h4>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', width: '100%', maxWidth: 760 }}>
          <thead>
            <tr>
              <th style={{ ...headCell, width: '26%' }}>{groupLabel}</th>
              <th style={headCell}>{itemLabel}</th>
              <th style={{ ...headCell, textAlign: 'right', width: '12%' }}>Score</th>
            </tr>
          </thead>
          <tbody>
            {order.map((cat) =>
              byCategory[cat].map((row, idx) => {
                const muted = row.status === 'no_evidence';
                return (
                  <tr key={row.dimension}>
                    {idx === 0 && (
                      <td
                        rowSpan={byCategory[cat].length}
                        style={{
                          ...cell,
                          fontWeight: 700,
                          color: '#02664b',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {cat}
                      </td>
                    )}
                    <td style={{ ...cell, color: muted ? '#aab2ae' : '#334' }}>
                      {row.dimension}
                    </td>
                    <td
                      style={{
                        ...cell,
                        textAlign: 'right',
                        fontWeight: 700,
                        whiteSpace: 'nowrap',
                        color: muted ? '#aab2ae' : '#02664b',
                      }}
                    >
                      {muted ? '—' : row.score}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default SkillsDetailTable;
