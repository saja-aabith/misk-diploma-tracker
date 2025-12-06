import React from 'react';
import './QuadrantCircle.css';

function QuadrantCircle3D({ size = 500 }) {
  const quadrants = [
    { 
      name: 'Academic', 
      color: '#E74C3C',
      icon: '🎓',
      label: '(AP)'
    },
    { 
      name: 'Internship', 
      color: '#9B59B6',
      icon: '⚙️',
      label: ''
    },
    { 
      name: 'National Identity', 
      color: '#2ECC71',
      icon: '🇸🇦',
      label: ''
    },
    { 
      name: 'Leadership', 
      color: '#F39C12',
      icon: '🏛️',
      label: ''
    }
  ];

  const containerStyle = {
    width: size,
    height: size,
    position: 'relative',
    margin: '0 auto',
    zIndex: 10,
    filter: 'drop-shadow(0 0 30px rgba(0, 0, 0, 0.15)) drop-shadow(0 0 60px rgba(2, 102, 75, 0.1))'
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
    zIndex: 20
  });

  return (
    <div style={containerStyle}>
      <svg width={size} height={size} viewBox="0 0 500 500">
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

          {/* Enhanced Glow filter */}
          <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="8" result="coloredBlur"/>
            <feMerge>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>

          {/* Stronger outer glow */}
          <filter id="outerGlow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur in="SourceAlpha" stdDeviation="10"/>
            <feOffset dx="0" dy="0" result="offsetblur"/>
            <feComponentTransfer>
              <feFuncA type="linear" slope="0.8"/>
            </feComponentTransfer>
            <feMerge>
              <feMergeNode/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>

          {/* Shadow filter */}
          <filter id="shadow">
            <feDropShadow dx="0" dy="6" stdDeviation="10" floodOpacity="0.25"/>
          </filter>

          {/* Curved text paths for each quadrant */}
          {/* Academic path - curves from top to right */}
          <path 
            id="academicPath" 
            d="M 250 95 A 155 155 0 0 1 405 250" 
            fill="none"
          />
          
          {/* Internship path - curves from right to bottom */}
          <path 
            id="internshipPath" 
            d="M 405 250 A 155 155 0 0 1 250 405" 
            fill="none"
          />
          
          {/* National Identity path - curves from bottom to left */}
          <path 
            id="identityPath" 
            d="M 250 405 A 155 155 0 0 1 95 250" 
            fill="none"
          />
          
          {/* Leadership path - curves from left to top */}
          <path 
            id="leadershipPath" 
            d="M 95 250 A 155 155 0 0 1 250 95" 
            fill="none"
          />
        </defs>

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

        {/* Academic - Top Right Quarter Circle */}
        <path
          d="M 250 250 L 250 60 A 190 190 0 0 1 440 250 Z"
          fill="url(#academicGrad)"
          filter="url(#glow)"
          className="quadrant-segment"
        />

        {/* Internship - Bottom Right Quarter Circle */}
        <path
          d="M 250 250 L 440 250 A 190 190 0 0 1 250 440 Z"
          fill="url(#internshipGrad)"
          filter="url(#glow)"
          className="quadrant-segment"
        />

        {/* National Identity - Bottom Left Quarter Circle */}
        <path
          d="M 250 250 L 250 440 A 190 190 0 0 1 60 250 Z"
          fill="url(#identityGrad)"
          filter="url(#glow)"
          className="quadrant-segment"
        />

        {/* Leadership - Top Left Quarter Circle */}
        <path
          d="M 250 250 L 60 250 A 190 190 0 0 1 250 60 Z"
          fill="url(#leadershipGrad)"
          filter="url(#glow)"
          className="quadrant-segment"
        />

        {/* Curved text labels */}
        
        {/* Academic - curved along top arc */}
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

        {/* Internship - curved along right arc */}
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

        {/* National Identity - curved along bottom arc */}
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

        {/* Leadership - curved along left arc */}
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

        {/* Center white circle with enhanced shadow */}
        <circle 
          cx="250" 
          cy="250" 
          r="95" 
          fill="white" 
          filter="url(#shadow)"
        />

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

      {/* Icon badges around the circle with enhanced glow */}
      {/* Academic - Top */}
      <div 
        style={{
          ...iconBadgeStyle(quadrants[0].color),
          top: '-15px',
          left: '50%',
          transform: 'translateX(-50%)'
        }}
        className="icon-badge icon-badge-pulse"
      >
        <div style={{ textAlign: 'center' }}>
          <div>{quadrants[0].icon}</div>
          {quadrants[0].label && (
            <div style={{ 
              fontSize: '10px', 
              color: quadrants[0].color, 
              fontWeight: 'bold',
              marginTop: '2px'
            }}>
              {quadrants[0].label}
            </div>
          )}
        </div>
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
      >
        {quadrants[3].icon}
      </div>
    </div>
  );
}

export default QuadrantCircle3D;