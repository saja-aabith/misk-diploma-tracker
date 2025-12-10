import React, { useState } from 'react';
import './QuadrantCircle.css';
import { BookOpenCheck, BriefcaseBusiness, Landmark, Mountain } from 'lucide-react';

function QuadrantCircle3D({ size = 500 }) {
  const [tilt, setTilt] = useState({ x: 0, y: 0 });
  const [hoveredQuadrant, setHoveredQuadrant] = useState(null);

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

  return (
    <div className="quadrant-hologram-wrapper">
      <div
        style={containerStyle}
        className="quadrant-hologram-core"
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      >
        <svg
          className="quadrant-svg"
          width={size}
          height={size}
          viewBox="0 0 500 500"
        >
          <defs>
            {/* Enhanced Gradients for each quadrant */}
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

            {/* Curved text paths */}
            <path id="academicPath" d="M 250 95 A 155 155 0 0 1 405 250" fill="none" />
            <path id="internshipPath" d="M 405 250 A 155 155 0 0 1 250 405" fill="none" />
            <path id="identityPath" d="M 250 405 A 155 155 0 0 1 95 250" fill="none" />
            <path id="leadershipPath" d="M 95 250 A 155 155 0 0 1 250 95" fill="none" />
          </defs>

          {/* Hologram circuit layer behind everything */}
          <g className="circuit-layer">
            <circle
              cx="250"
              cy="250"
              r="170"
              className="circuit-ring circuit-ring--outer"
            />
            <circle
              cx="250"
              cy="250"
              r="140"
              className="circuit-ring circuit-ring--inner"
            />
            <circle
              cx="250"
              cy="250"
              r="115"
              className="circuit-ring circuit-ring--dashed"
            />

            {/* Spokes */}
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

          {/* Quadrant segments with hover handlers */}
          <path
            d="M 250 250 L 250 60 A 190 190 0 0 1 440 250 Z"
            fill="url(#academicGrad)"
            filter="url(#glow)"
            className="quadrant-segment"
            onMouseEnter={() => setHoveredQuadrant(quadrants[0])}
            onMouseLeave={() => setHoveredQuadrant(null)}
          />
          <path
            d="M 250 250 L 440 250 A 190 190 0 0 1 250 440 Z"
            fill="url(#internshipGrad)"
            filter="url(#glow)"
            className="quadrant-segment"
            onMouseEnter={() => setHoveredQuadrant(quadrants[1])}
            onMouseLeave={() => setHoveredQuadrant(null)}
          />
          <path
            d="M 250 250 L 250 440 A 190 190 0 0 1 60 250 Z"
            fill="url(#identityGrad)"
            filter="url(#glow)"
            className="quadrant-segment"
            onMouseEnter={() => setHoveredQuadrant(quadrants[2])}
            onMouseLeave={() => setHoveredQuadrant(null)}
          />
          <path
            d="M 250 250 L 60 250 A 190 190 0 0 1 250 60 Z"
            fill="url(#leadershipGrad)"
            filter="url(#glow)"
            className="quadrant-segment"
            onMouseEnter={() => setHoveredQuadrant(quadrants[3])}
            onMouseLeave={() => setHoveredQuadrant(null)}
          />

          {/* Curved text labels */}
          <text
            fill="white"
            fontSize="18"
            fontWeight="bold"
            letterSpacing="2"
            style={{ filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.4))' }}
          >
            <textPath href="#academicPath" startOffset="50%" textAnchor="middle">
              Academic
            </textPath>
          </text>

          <text
            fill="white"
            fontSize="18"
            fontWeight="bold"
            letterSpacing="2"
            style={{ filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.4))' }}
          >
            <textPath href="#internshipPath" startOffset="50%" textAnchor="middle">
              Internship
            </textPath>
          </text>

          <text
            fill="white"
            fontSize="16"
            fontWeight="bold"
            letterSpacing="1"
            style={{ filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.4))' }}
          >
            <textPath href="#identityPath" startOffset="50%" textAnchor="middle">
              National Identity
            </textPath>
          </text>

          <text
            fill="white"
            fontSize="18"
            fontWeight="bold"
            letterSpacing="2"
            style={{ filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.4))' }}
          >
            <textPath href="#leadershipPath" startOffset="50%" textAnchor="middle">
              Leadership
            </textPath>
          </text>

          {/* Core hologram arcs */}
          <g className="core-arcs">
            <circle cx="250" cy="250" r="115" className="core-arc core-arc--one" />
            <circle cx="250" cy="250" r="125" className="core-arc core-arc--two" />
          </g>

          {/* Center white circle */}
          <circle cx="250" cy="250" r="95" fill="white" filter="url(#shadow)" />

          {/* Center text */}
          <text
            x="250"
            y="235"
            textAnchor="middle"
            fill="#666"
            fontSize="18"
            fontWeight="500"
            letterSpacing="0.5"
          >
            Misk Schools
          </text>
          <text
            x="250"
            y="260"
            textAnchor="middle"
            fill="#02664b"
            fontSize="22"
            fontWeight="bold"
          >
            Diploma
          </text>
        </svg>

        {/* Icon badges */}

        {/* Academic - Top */}
        <div
          style={{
            ...iconBadgeStyle(quadrants[0].color),
            top: '-15px',
            left: '50%',
            transform: 'translateX(-50%)'
          }}
          className="icon-badge icon-badge-pulse"
          onMouseEnter={() => setHoveredQuadrant(quadrants[0])}
          onMouseLeave={() => setHoveredQuadrant(null)}
        >
          {quadrants[0].icon}
        </div>

        {/* Internship - Right */}
        <div
          style={{
            ...iconBadgeStyle(quadrants[1].color),
            top: '50%',
            right: '-15px',
            transform: 'translateY(-50%)'
          }}
          className="icon-badge icon-badge-pulse"
          onMouseEnter={() => setHoveredQuadrant(quadrants[1])}
          onMouseLeave={() => setHoveredQuadrant(null)}
        >
          {quadrants[1].icon}
        </div>

        {/* National Identity - Bottom */}
        <div
          style={{
            ...iconBadgeStyle(quadrants[2].color),
            bottom: '-15px',
            left: '50%',
            transform: 'translateX(-50%)'
          }}
          className="icon-badge icon-badge-pulse"
          onMouseEnter={() => setHoveredQuadrant(quadrants[2])}
          onMouseLeave={() => setHoveredQuadrant(null)}
        >
          {quadrants[2].icon}
        </div>

        {/* Leadership - Left */}
        <div
          style={{
            ...iconBadgeStyle(quadrants[3].color),
            top: '50%',
            left: '-15px',
            transform: 'translateY(-50%)'
          }}
          className="icon-badge icon-badge-pulse"
          onMouseEnter={() => setHoveredQuadrant(quadrants[3])}
          onMouseLeave={() => setHoveredQuadrant(null)}
        >
          {quadrants[3].icon}
        </div>

        {/* Tooltip chip positioned by quadrant side */}
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
