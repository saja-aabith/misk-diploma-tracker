import React, { useState, useMemo } from 'react';
import './QuadrantCircle.css';
import { BookOpenCheck, BriefcaseBusiness, Landmark, Mountain } from 'lucide-react';

function QuadrantCircle3D({ size = 620, onMiskCoreClick }) {
  const [tilt, setTilt] = useState({ x: 0, y: 0 });
  const [hoveredQuadrant, setHoveredQuadrant] = useState(null);

  const scale = useMemo(() => Math.max(1, size / 500), [size]);

  const badgeSize = Math.round(90 * scale);
  const badgeIconSize = Math.round(40 * scale);

  const labelSizeMain = Math.round(18 * scale);
  const labelSizeSmall = Math.round(16 * scale);

  const coreTitleSize = Math.round(24 * scale);
  const coreSubSize = Math.round(12 * scale);

  const miskCore = {
    name: 'Misk Core',
    side: 'center',
    tooltip:
      'Captures CCAP, trips, competitions, Project 10, and other whole-school experiences linked across all four quadrants.'
  };

  // Order (clockwise from TOP-LEFT): Academic, Internship, National Identity, Leadership
  const quadrants = [
    {
      name: 'Academic',
      color: '#E74C3C',
      icon: <BookOpenCheck className="sketch-icon" size={badgeIconSize} />,
      label: '',
      side: 'top',
      tooltip:
        'IGCSE, IAL, national exams (NAFS G6/G9, Qudrat, Tahsili) and EPQ-style research projects.'
    },
    {
      name: 'Internship',
      color: '#9B59B6',
      icon: <BriefcaseBusiness className="sketch-icon" size={badgeIconSize} />,
      label: '',
      side: 'right',
      tooltip:
        'Industry internship reports and multi-year career planning towards your future pathways.'
    },
    {
      name: 'National Identity',
      color: '#2ECC71',
      icon: <Landmark className="sketch-icon" size={badgeIconSize} />,
      label: '',
      side: 'bottom',
      tooltip:
        'Arabic language development and deep engagement with Saudi national heritage and culture.'
    },
    {
      name: 'Leadership',
      color: '#F39C12',
      icon: <Mountain className="sketch-icon" size={badgeIconSize} />,
      label: '',
      side: 'left',
      tooltip:
        'CMI-linked leadership competencies and advanced presentation skills in real projects.'
    }
  ];

  const handleMouseMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;
    const maxTilt = 10;

    setTilt({
      x: y * maxTilt,
      y: -x * maxTilt
    });
  };

  const handleMouseLeave = () => {
    setTilt({ x: 0, y: 0 });
    setHoveredQuadrant(null);
  };

  // Misk Core center is clickable only when the parent passes a handler.
  // When clickable, the surface circle behaves like a button (focusable,
  // Enter/Space activates) and the title text is also click-targeted so
  // users can land on either; the title intentionally stays non-focusable
  // to avoid duplicate tab stops for the same action.
  const isCenterClickable = typeof onMiskCoreClick === 'function';

  const handleCenterKeyDown = (e) => {
    if (!isCenterClickable) return;
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onMiskCoreClick();
    }
  };

  const containerStyle = {
    width: size,
    height: size,
    position: 'relative',
    margin: '0 auto',
    zIndex: 10,
    filter:
      'drop-shadow(0 0 30px rgba(0, 0, 0, 0.15)) drop-shadow(0 0 60px rgba(2, 102, 75, 0.1))',
    transformStyle: 'preserve-3d',
    transform: `rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)`,
    transition: 'transform 0.25s ease-out'
  };

  const iconBadgeStyle = (color) => ({
    position: 'absolute',
    width: `${badgeSize}px`,
    height: `${badgeSize}px`,
    borderRadius: '50%',
    background: 'white',
    border: `${Math.max(3, Math.round(4 * scale))}px solid ${color}`,
    boxShadow: `0 8px 24px rgba(0, 0, 0, 0.15), 0 0 20px ${color}40`,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'all 0.3s ease',
    cursor: 'pointer',
    zIndex: 20,
    color
  });

  // Segment mapping (matches your layout)
  const SEG_TOP_RIGHT = quadrants[1]; // Internship
  const SEG_BOTTOM_RIGHT = quadrants[2]; // National Identity
  const SEG_BOTTOM_LEFT = quadrants[3]; // Leadership
  const SEG_TOP_LEFT = quadrants[0]; // Academic

  const cornerOffset = Math.round(70 * scale);

  return (
    <div className="quadrant-hologram-wrapper">
      <div
        style={containerStyle}
        className="quadrant-hologram-core"
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      >
        <svg className="quadrant-svg" width={size} height={size} viewBox="0 0 500 500">
          <defs>
            {/* Quadrant gradients */}
            <linearGradient id="academicGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" style={{ stopColor: '#E74C3C', stopOpacity: 1 }} />
              <stop offset="100%" style={{ stopColor: '#C0392B', stopOpacity: 1 }} />
            </linearGradient>
            <linearGradient id="internshipGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" style={{ stopColor: '#9B59B6', stopOpacity: 1 }} />
              <stop offset="100%" style={{ stopColor: '#8E44AD', stopOpacity: 1 }} />
            </linearGradient>
            <linearGradient id="identityGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" style={{ stopColor: '#2ECC71', stopOpacity: 1 }} />
              <stop offset="100%" style={{ stopColor: '#27AE60', stopOpacity: 1 }} />
            </linearGradient>
            <linearGradient id="leadershipGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" style={{ stopColor: '#F39C12', stopOpacity: 1 }} />
              <stop offset="100%" style={{ stopColor: '#E67E22', stopOpacity: 1 }} />
            </linearGradient>

            {/* Center surface */}
            <radialGradient id="miskCoreGrad" cx="50%" cy="40%" r="70%">
              <stop offset="0%" stopColor="#FFFFFF" />
              <stop offset="60%" stopColor="#F5FFFB" />
              <stop offset="100%" stopColor="#E6FFF6" />
            </radialGradient>

            {/* Futuristic neon root gradients */}
            <linearGradient id="rootGradTR" x1="250" y1="250" x2="365" y2="135" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="rgba(0,214,160,0.85)" />
              <stop offset="55%" stopColor="rgba(0,214,160,0.35)" />
              <stop offset="100%" stopColor="rgba(0,214,160,0.08)" />
            </linearGradient>
            <linearGradient id="rootGradBR" x1="250" y1="250" x2="365" y2="365" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="rgba(0,214,160,0.85)" />
              <stop offset="55%" stopColor="rgba(0,214,160,0.35)" />
              <stop offset="100%" stopColor="rgba(0,214,160,0.08)" />
            </linearGradient>
            <linearGradient id="rootGradBL" x1="250" y1="250" x2="135" y2="365" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="rgba(0,214,160,0.85)" />
              <stop offset="55%" stopColor="rgba(0,214,160,0.35)" />
              <stop offset="100%" stopColor="rgba(0,214,160,0.08)" />
            </linearGradient>
            <linearGradient id="rootGradTL" x1="250" y1="250" x2="135" y2="135" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="rgba(0,214,160,0.85)" />
              <stop offset="55%" stopColor="rgba(0,214,160,0.35)" />
              <stop offset="100%" stopColor="rgba(0,214,160,0.08)" />
            </linearGradient>

            {/* Glows */}
            <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="8" result="coloredBlur" />
              <feMerge>
                <feMergeNode in="coloredBlur" />
                <feMergeNode in="coloredBlur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>

            <filter id="outerGlow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur in="SourceAlpha" stdDeviation="10" />
              <feOffset dx="0" dy="0" result="offsetblur" />
              <feComponentTransfer>
                <feFuncA type="linear" slope="0.8" />
              </feComponentTransfer>
              <feMerge>
                <feMergeNode />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>

            <filter id="shadow">
              <feDropShadow dx="0" dy="6" stdDeviation="10" floodOpacity="0.25" />
            </filter>

            <filter id="rootNeon" x="-120%" y="-120%" width="340%" height="340%">
              <feDropShadow dx="0" dy="0" stdDeviation="6" floodColor="#00D6A0" floodOpacity="0.65" />
              <feDropShadow dx="0" dy="0" stdDeviation="14" floodColor="#00D6A0" floodOpacity="0.35" />
              <feDropShadow dx="0" dy="10" stdDeviation="14" floodColor="#000000" floodOpacity="0.18" />
            </filter>

            <filter id="coreGlow" x="-80%" y="-80%" width="260%" height="260%">
              <feDropShadow dx="0" dy="0" stdDeviation="10" floodColor="#00D6A0" floodOpacity="0.40" />
              <feDropShadow dx="0" dy="0" stdDeviation="22" floodColor="#00D6A0" floodOpacity="0.20" />
              <feDropShadow dx="0" dy="12" stdDeviation="16" floodColor="#000000" floodOpacity="0.16" />
            </filter>

            {/* Curved text paths */}
            <path id="academicPath" d="M 250 95 A 155 155 0 0 1 405 250" fill="none" />
            <path id="internshipPath" d="M 405 250 A 155 155 0 0 1 250 405" fill="none" />
            <path id="identityPath" d="M 250 405 A 155 155 0 0 1 95 250" fill="none" />
            <path id="leadershipPath" d="M 95 250 A 155 155 0 0 1 250 95" fill="none" />
          </defs>

          {/* Circuit layer */}
          <g className="circuit-layer">
            <circle cx="250" cy="250" r="170" className="circuit-ring circuit-ring--outer" />
            <circle cx="250" cy="250" r="140" className="circuit-ring circuit-ring--inner" />
            <circle cx="250" cy="250" r="115" className="circuit-ring circuit-ring--dashed" />
            <line x1="250" y1="80" x2="250" y2="110" className="circuit-spoke" />
            <line x1="250" y1="390" x2="250" y2="420" className="circuit-spoke" />
            <line x1="80" y1="250" x2="110" y2="250" className="circuit-spoke" />
            <line x1="390" y1="250" x2="420" y2="250" className="circuit-spoke" />
            <line x1="140" y1="140" x2="165" y2="165" className="circuit-spoke" />
            <line x1="360" y1="140" x2="335" y2="165" className="circuit-spoke" />
            <line x1="140" y1="360" x2="165" y2="335" className="circuit-spoke" />
            <line x1="360" y1="360" x2="335" y2="335" className="circuit-spoke" />
          </g>

          {/* Outer glow */}
          <circle
            cx="250"
            cy="250"
            r="200"
            fill="none"
            stroke="rgba(2, 102, 75, 0.2)"
            strokeWidth="8"
            opacity="0.5"
            filter="url(#outerGlow)"
          />

          {/* Quadrants */}
          <path
            d="M 250 250 L 250 60 A 190 190 0 0 1 440 250 Z"
            fill="url(#internshipGrad)"
            filter="url(#glow)"
            className="quadrant-segment"
            onMouseEnter={() => setHoveredQuadrant(SEG_TOP_RIGHT)}
            onMouseLeave={() => setHoveredQuadrant(null)}
          />
          <path
            d="M 250 250 L 440 250 A 190 190 0 0 1 250 440 Z"
            fill="url(#identityGrad)"
            filter="url(#glow)"
            className="quadrant-segment"
            onMouseEnter={() => setHoveredQuadrant(SEG_BOTTOM_RIGHT)}
            onMouseLeave={() => setHoveredQuadrant(null)}
          />
          <path
            d="M 250 250 L 250 440 A 190 190 0 0 1 60 250 Z"
            fill="url(#leadershipGrad)"
            filter="url(#glow)"
            className="quadrant-segment"
            onMouseEnter={() => setHoveredQuadrant(SEG_BOTTOM_LEFT)}
            onMouseLeave={() => setHoveredQuadrant(null)}
          />
          <path
            d="M 250 250 L 60 250 A 190 190 0 0 1 250 60 Z"
            fill="url(#academicGrad)"
            filter="url(#glow)"
            className="quadrant-segment"
            onMouseEnter={() => setHoveredQuadrant(SEG_TOP_LEFT)}
            onMouseLeave={() => setHoveredQuadrant(null)}
          />

          {/* Labels (scaled) */}
          <text fill="white" fontSize={labelSizeMain} fontWeight="bold" letterSpacing="2" style={{ filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.4))' }}>
            <textPath href="#academicPath" startOffset="50%" textAnchor="middle">
              {SEG_TOP_RIGHT.name}
            </textPath>
          </text>

          <text fill="white" fontSize={labelSizeSmall} fontWeight="bold" letterSpacing="1" style={{ filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.4))' }}>
            <textPath href="#internshipPath" startOffset="50%" textAnchor="middle">
              {SEG_BOTTOM_RIGHT.name}
            </textPath>
          </text>

          <text fill="white" fontSize={labelSizeMain} fontWeight="bold" letterSpacing="2" style={{ filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.4))' }}>
            <textPath href="#identityPath" startOffset="50%" textAnchor="middle">
              {SEG_BOTTOM_LEFT.name}
            </textPath>
          </text>

          <text fill="white" fontSize={labelSizeMain} fontWeight="bold" letterSpacing="2" style={{ filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.4))' }}>
            <textPath href="#leadershipPath" startOffset="50%" textAnchor="middle">
              {SEG_TOP_LEFT.name}
            </textPath>
          </text>

          {/* Roots */}
          <g className="misk-root-network" filter="url(#rootNeon)" pointerEvents="none">
            <path d="M 250 250 C 228 228, 195 200, 150 150" stroke="url(#rootGradTL)" strokeWidth="5" strokeLinecap="round" fill="none" className="root-flow root-flow--a" />
            <path d="M 235 235 C 210 218, 182 190, 160 165" stroke="url(#rootGradTL)" strokeWidth="3" strokeLinecap="round" fill="none" className="root-flow root-flow--b" />

            <path d="M 250 250 C 272 228, 305 200, 350 150" stroke="url(#rootGradTR)" strokeWidth="5" strokeLinecap="round" fill="none" className="root-flow root-flow--a" />
            <path d="M 265 235 C 290 218, 318 190, 340 165" stroke="url(#rootGradTR)" strokeWidth="3" strokeLinecap="round" fill="none" className="root-flow root-flow--c" />

            <path d="M 250 250 C 272 272, 305 300, 350 350" stroke="url(#rootGradBR)" strokeWidth="5" strokeLinecap="round" fill="none" className="root-flow root-flow--a" />
            <path d="M 265 265 C 290 282, 320 312, 342 338" stroke="url(#rootGradBR)" strokeWidth="3" strokeLinecap="round" fill="none" className="root-flow root-flow--b" />

            <path d="M 250 250 C 228 272, 195 300, 150 350" stroke="url(#rootGradBL)" strokeWidth="5" strokeLinecap="round" fill="none" className="root-flow root-flow--a" />
            <path d="M 235 265 C 210 282, 180 312, 158 338" stroke="url(#rootGradBL)" strokeWidth="3" strokeLinecap="round" fill="none" className="root-flow root-flow--c" />

            <circle cx="150" cy="150" r="4.5" fill="rgba(0,214,160,0.85)" className="root-node" />
            <circle cx="350" cy="150" r="4.5" fill="rgba(0,214,160,0.85)" className="root-node" />
            <circle cx="350" cy="350" r="4.5" fill="rgba(0,214,160,0.85)" className="root-node" />
            <circle cx="150" cy="350" r="4.5" fill="rgba(0,214,160,0.85)" className="root-node" />
          </g>

          {/* Rings */}
          <circle cx="250" cy="250" r="112" fill="none" stroke="rgba(0,214,160,0.35)" strokeWidth="3" strokeDasharray="9 12" className="misk-core-rings" pointerEvents="none" />
          <circle cx="250" cy="250" r="103" fill="none" stroke="rgba(0,214,160,0.16)" strokeWidth="10" pointerEvents="none" />

          {/* Center — clickable when onMiskCoreClick is provided.
              The surface circle behaves like a button (focusable,
              Enter/Space activates); the title (below) shares the
              click target without taking a separate tab stop. */}
          <circle
            cx="250"
            cy="250"
            r="95"
            fill="url(#miskCoreGrad)"
            filter="url(#coreGlow)"
            className="misk-core-surface"
            style={{ cursor: 'pointer' }}
            onMouseEnter={() => setHoveredQuadrant(miskCore)}
            onMouseLeave={() => setHoveredQuadrant(null)}
            onClick={isCenterClickable ? onMiskCoreClick : undefined}
            onKeyDown={isCenterClickable ? handleCenterKeyDown : undefined}
            role={isCenterClickable ? 'button' : undefined}
            tabIndex={isCenterClickable ? 0 : undefined}
            aria-label={isCenterClickable ? 'Open Misk Core activity log' : undefined}
          />
          <circle cx="235" cy="235" r="55" fill="rgba(255,255,255,0.35)" pointerEvents="none" />

          {/* PERFECTLY CENTERED TITLE (2 lines) */}
          <text
            x="250"
            y="250"
            textAnchor="middle"
            dominantBaseline="middle"
            fill="#02664b"
            fontWeight="900"
            letterSpacing="0.4"
            className="misk-core-title"
            style={{ cursor: 'pointer' }}
            onMouseEnter={() => setHoveredQuadrant(miskCore)}
            onMouseLeave={() => setHoveredQuadrant(null)}
            onClick={isCenterClickable ? onMiskCoreClick : undefined}
          >
            <tspan x="250" dy={-(coreSubSize * 0.35)} fontSize={coreTitleSize}>
              Misk Core
            </tspan>
            <tspan x="250" dy={coreSubSize * 1.35} fontSize={coreSubSize} fill="#0a5c49" opacity="0.9" fontWeight="800">
              Linked experiences
            </tspan>
          </text>
        </svg>

        {/* Icon badges (scaled + positioned) */}
        <div
          style={{ ...iconBadgeStyle(quadrants[0].color), top: `${cornerOffset}px`, left: `${cornerOffset}px`, transform: 'translate(-50%, -50%)' }}
          className="icon-badge icon-badge-pulse"
          onMouseEnter={() => setHoveredQuadrant(quadrants[0])}
          onMouseLeave={() => setHoveredQuadrant(null)}
        >
          {quadrants[0].icon}
        </div>

        <div
          style={{ ...iconBadgeStyle(quadrants[1].color), top: `${cornerOffset}px`, right: `${cornerOffset}px`, transform: 'translate(50%, -50%)' }}
          className="icon-badge icon-badge-pulse"
          onMouseEnter={() => setHoveredQuadrant(quadrants[1])}
          onMouseLeave={() => setHoveredQuadrant(null)}
        >
          {quadrants[1].icon}
        </div>

        <div
          style={{ ...iconBadgeStyle(quadrants[2].color), bottom: `${cornerOffset}px`, right: `${cornerOffset}px`, transform: 'translate(50%, 50%)' }}
          className="icon-badge icon-badge-pulse"
          onMouseEnter={() => setHoveredQuadrant(quadrants[2])}
          onMouseLeave={() => setHoveredQuadrant(null)}
        >
          {quadrants[2].icon}
        </div>

        <div
          style={{ ...iconBadgeStyle(quadrants[3].color), bottom: `${cornerOffset}px`, left: `${cornerOffset}px`, transform: 'translate(-50%, 50%)' }}
          className="icon-badge icon-badge-pulse"
          onMouseEnter={() => setHoveredQuadrant(quadrants[3])}
          onMouseLeave={() => setHoveredQuadrant(null)}
        >
          {quadrants[3].icon}
        </div>

        {/* Tooltip */}
        {hoveredQuadrant && (
          <div className={`quadrant-tooltip tooltip-${hoveredQuadrant.side}`}>
            <div className="quadrant-tooltip-title">{hoveredQuadrant.name}</div>
            <div className="quadrant-tooltip-body">{hoveredQuadrant.tooltip}</div>
          </div>
        )}
      </div>
    </div>
  );
}

export default QuadrantCircle3D;