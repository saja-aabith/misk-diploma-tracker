import React, { useState } from 'react';
import './QuadrantCircle.css';
import { BookOpenCheck, BriefcaseBusiness, Landmark, Mountain } from 'lucide-react';

function QuadrantCircle3D({ size = 500 }) {
  const [tilt, setTilt] = useState({ x: 0, y: 0 });
  const [hoveredQuadrant, setHoveredQuadrant] = useState(null);

  // Center category (shared across all quadrants)
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
      icon: <BookOpenCheck className="sketch-icon" size={40} />,
      label: '',
      side: 'top',
      tooltip:
        'IGCSE, IAL, national exams (NAFS G6/G9, Qudrat, Tahsili) and EPQ-style research projects.'
    },
    {
      name: 'Internship',
      color: '#9B59B6',
      icon: <BriefcaseBusiness className="sketch-icon" size={40} />,
      label: '',
      side: 'right',
      tooltip:
        'Industry internship reports and multi-year career planning towards your future pathways.'
    },
    {
      name: 'National Identity',
      color: '#2ECC71',
      icon: <Landmark className="sketch-icon" size={40} />,
      label: '',
      side: 'bottom',
      tooltip:
        'Arabic language development and deep engagement with Saudi national heritage and culture.'
    },
    {
      name: 'Leadership',
      color: '#F39C12',
      icon: <Mountain className="sketch-icon" size={40} />,
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
    width: '90px',
    height: '90px',
    borderRadius: '50%',
    background: 'white',
    border: `4px solid ${color}`,
    boxShadow: `0 8px 24px rgba(0, 0, 0, 0.15), 0 0 20px ${color}40`,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '36px',
    transition: 'all 0.3s ease',
    cursor: 'pointer',
    zIndex: 20,
    color
  });

  // Segment mapping to match your image layout
  const SEG_TOP_RIGHT = quadrants[1]; // Internship
  const SEG_BOTTOM_RIGHT = quadrants[2]; // National Identity
  const SEG_BOTTOM_LEFT = quadrants[3]; // Leadership
  const SEG_TOP_LEFT = quadrants[0]; // Academic

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
            {/* Gradients */}
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

            {/* Modern “Misk Core” radial fill */}
            <radialGradient id="miskCoreGrad" cx="50%" cy="40%" r="70%">
              <stop offset="0%" stopColor="#FFFFFF" />
              <stop offset="60%" stopColor="#F5FFFB" />
              <stop offset="100%" stopColor="#E6FFF6" />
            </radialGradient>

            {/* Glow filter */}
            <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="8" result="coloredBlur" />
              <feMerge>
                <feMergeNode in="coloredBlur" />
                <feMergeNode in="coloredBlur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>

            {/* Stronger outer glow */}
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

            {/* Shadow filter */}
            <filter id="shadow">
              <feDropShadow dx="0" dy="6" stdDeviation="10" floodOpacity="0.25" />
            </filter>

            {/* NEW: Futuristic center glow */}
            <filter id="coreGlow" x="-80%" y="-80%" width="260%" height="260%">
              <feDropShadow dx="0" dy="0" stdDeviation="10" floodColor="#00D6A0" floodOpacity="0.45" />
              <feDropShadow dx="0" dy="0" stdDeviation="20" floodColor="#00D6A0" floodOpacity="0.22" />
              <feDropShadow dx="0" dy="10" stdDeviation="14" floodColor="#000000" floodOpacity="0.18" />
            </filter>

            {/* Curved text paths (POSITION paths) */}
            <path id="academicPath" d="M 250 95 A 155 155 0 0 1 405 250" fill="none" /> {/* top-right */}
            <path id="internshipPath" d="M 405 250 A 155 155 0 0 1 250 405" fill="none" /> {/* bottom-right */}
            <path id="identityPath" d="M 250 405 A 155 155 0 0 1 95 250" fill="none" /> {/* bottom-left */}
            <path id="leadershipPath" d="M 95 250 A 155 155 0 0 1 250 95" fill="none" /> {/* top-left */}
          </defs>

          {/* Hologram circuit layer behind everything */}
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

          {/* Outer glow circle */}
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

          {/* Quadrant segments */}
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

          {/* Curved text labels */}
          <text fill="white" fontSize="18" fontWeight="bold" letterSpacing="2" style={{ filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.4))' }}>
            <textPath href="#academicPath" startOffset="50%" textAnchor="middle">
              {SEG_TOP_RIGHT.name}
            </textPath>
          </text>

          <text fill="white" fontSize="16" fontWeight="bold" letterSpacing="1" style={{ filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.4))' }}>
            <textPath href="#internshipPath" startOffset="50%" textAnchor="middle">
              {SEG_BOTTOM_RIGHT.name}
            </textPath>
          </text>

          <text fill="white" fontSize="18" fontWeight="bold" letterSpacing="2" style={{ filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.4))' }}>
            <textPath href="#identityPath" startOffset="50%" textAnchor="middle">
              {SEG_BOTTOM_LEFT.name}
            </textPath>
          </text>

          <text fill="white" fontSize="18" fontWeight="bold" letterSpacing="2" style={{ filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.4))' }}>
            <textPath href="#leadershipPath" startOffset="50%" textAnchor="middle">
              {SEG_TOP_LEFT.name}
            </textPath>
          </text>

          {/* ===== NEW: Futuristic center system (rings + glow) ===== */}
          {/* Rotating dashed ring */}
          <circle
            cx="250"
            cy="250"
            r="112"
            fill="none"
            stroke="rgba(0, 214, 160, 0.45)"
            strokeWidth="3"
            strokeDasharray="10 12"
            className="misk-core-orbit"
          />

          {/* Solid accent ring */}
          <circle
            cx="250"
            cy="250"
            r="103"
            fill="none"
            stroke="rgba(0, 214, 160, 0.22)"
            strokeWidth="10"
            className="misk-core-ring"
          />

          {/* Center circle (hoverable, glowing) */}
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
          />

          {/* Subtle inner highlight */}
          <circle
            cx="235"
            cy="235"
            r="55"
            fill="rgba(255,255,255,0.35)"
            className="misk-core-highlight"
            pointerEvents="none"
          />

          {/* Center title */}
          <text
            x="250"
            y="246"
            textAnchor="middle"
            fill="#02664b"
            fontSize="24"
            fontWeight="900"
            letterSpacing="0.4"
            className="misk-core-title"
            style={{ cursor: 'pointer' }}
            onMouseEnter={() => setHoveredQuadrant(miskCore)}
            onMouseLeave={() => setHoveredQuadrant(null)}
          >
            Misk Core
          </text>

          {/* Center subtitle */}
          <text
            x="250"
            y="272"
            textAnchor="middle"
            fill="#0a5c49"
            fontSize="12"
            fontWeight="600"
            letterSpacing="0.2"
            opacity="0.85"
            className="misk-core-subtitle"
            style={{ cursor: 'pointer' }}
            onMouseEnter={() => setHoveredQuadrant(miskCore)}
            onMouseLeave={() => setHoveredQuadrant(null)}
          >
            Cross-quadrant experiences
          </text>
        </svg>

        {/* Icon badges (4 corners) */}
        <div
          style={{ ...iconBadgeStyle(quadrants[0].color), top: '70px', left: '70px', transform: 'translate(-50%, -50%)' }}
          className="icon-badge icon-badge-pulse"
          onMouseEnter={() => setHoveredQuadrant(quadrants[0])}
          onMouseLeave={() => setHoveredQuadrant(null)}
        >
          {quadrants[0].icon}
        </div>

        <div
          style={{ ...iconBadgeStyle(quadrants[1].color), top: '70px', right: '70px', transform: 'translate(50%, -50%)' }}
          className="icon-badge icon-badge-pulse"
          onMouseEnter={() => setHoveredQuadrant(quadrants[1])}
          onMouseLeave={() => setHoveredQuadrant(null)}
        >
          {quadrants[1].icon}
        </div>

        <div
          style={{ ...iconBadgeStyle(quadrants[2].color), bottom: '70px', right: '70px', transform: 'translate(50%, 50%)' }}
          className="icon-badge icon-badge-pulse"
          onMouseEnter={() => setHoveredQuadrant(quadrants[2])}
          onMouseLeave={() => setHoveredQuadrant(null)}
        >
          {quadrants[2].icon}
        </div>

        <div
          style={{ ...iconBadgeStyle(quadrants[3].color), bottom: '70px', left: '70px', transform: 'translate(-50%, 50%)' }}
          className="icon-badge icon-badge-pulse"
          onMouseEnter={() => setHoveredQuadrant(quadrants[3])}
          onMouseLeave={() => setHoveredQuadrant(null)}
        >
          {quadrants[3].icon}
        </div>

        {/* Tooltip chip */}
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
