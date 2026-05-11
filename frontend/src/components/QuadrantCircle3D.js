import React, { useState, useEffect, useMemo } from 'react';
import './QuadrantCircle.css';
import { BookOpenCheck, BriefcaseBusiness, Landmark, Mountain } from 'lucide-react';

/**
 * QuadrantCircle3D
 *
 * Props:
 *   size: pixel size of the rendered SVG (default 620).
 *   onMiskCoreClick: optional click handler for the Misk Core center.
 *   completionByName: optional map of quadrant name -> completion %
 *     (0..100). Drives the radial-fill animation. When ABSENT or EMPTY,
 *     the component renders in "showcase mode": all five slices appear
 *     fully filled and no animation runs. Use case: hero / marketing
 *     visuals (e.g. the public homepage) that should look impressive
 *     rather than display real progress.
 *
 * Visual model:
 *   - Each quadrant slice is layered as (outline, filled-and-clipped).
 *     Empty slices show as hollow outlines; filling reveals the gradient
 *     fill radially from the center outward. The clip radius scales by
 *     SQRT of percentage so the *area* of the fill matches the
 *     percentage (radial linear scaling would under-fill visually).
 *   - Misk Core center has the white-ish base + a green inner fill
 *     circle that grows with completion. Misk Core title text fades
 *     from dark green (legible against the empty white-ish base) to
 *     white-with-shadow (legible against the green fill) as the fill
 *     grows, with linear interpolation across the 0..100% range.
 *   - On mount, all five fills animate from 0 to their target values
 *     with a small per-slice stagger (data-driven mode only).
 */
function QuadrantCircle3D({ size = 620, onMiskCoreClick, completionByName = {} }) {
  const [tilt, setTilt] = useState({ x: 0, y: 0 });
  const [hoveredQuadrant, setHoveredQuadrant] = useState(null);

  // Showcase mode: the component is being used as a hero visual, not a
  // status display. Trigger when no completion data is provided. In this
  // mode all slices render fully filled with no animation.
  //
  // Derived at every render (cheap object inspection) so callers who
  // mount the component initially without data and later pass it will
  // transition out of showcase mode cleanly. In practice this doesn't
  // happen — HomePage always omits the prop, StudentDashboard always
  // supplies it once dashboardData has loaded — but the derivation is
  // robust to either pattern.
  const showcaseMode = useMemo(
    () =>
      !completionByName ||
      typeof completionByName !== 'object' ||
      Object.keys(completionByName).length === 0,
    [completionByName]
  );

  // Displayed fill percentages. In data-driven mode these start at 0 and
  // animate to the target values via the staggered effect below. In
  // showcase mode they're seeded at 100 and never animated.
  //
  // useState's lazy initializer reads showcaseMode once at mount; later
  // toggles of showcaseMode (rare/impossible in practice) won't reset
  // displayedFills, which is acceptable behaviour for an edge case.
  const [displayedFills, setDisplayedFills] = useState(() => {
    const initial = showcaseMode ? 100 : 0;
    return {
      Academic: initial,
      Internship: initial,
      'National Identity': initial,
      Leadership: initial,
      'Misk Core': initial,
    };
  });

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

  // ---------------------------------------------------------------
  // Mount-time animation: stagger the five fills (data-driven mode).
  // ---------------------------------------------------------------
  // Skipped entirely in showcase mode (all-100 already set above).
  // Order is clockwise from top-left, with Misk Core last so the
  // demo narrative reads "the four quadrants fill, then the
  // connecting core fills."
  useEffect(() => {
    if (showcaseMode) return undefined;

    const STAGGER_MS = 200;
    const INITIAL_DELAY_MS = 80;
    const order = ['Academic', 'Internship', 'National Identity', 'Leadership', 'Misk Core'];

    const timeouts = order.map((name, idx) =>
      setTimeout(() => {
        setDisplayedFills((prev) => ({
          ...prev,
          [name]: clampPct(completionByName[name]),
        }));
      }, INITIAL_DELAY_MS + idx * STAGGER_MS)
    );

    return () => {
      timeouts.forEach((t) => clearTimeout(t));
    };
  }, [completionByName, showcaseMode]);

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

  // Per-name clip radius for the quadrant fills. Square-root scaling
  // ensures the *area* of the visible fill corresponds to the percentage
  // — at 50% the user sees half the slice area filled, not a quarter.
  const clipRadiusFor = (name) => pctToClipRadius(displayedFills[name]);

  // Misk Core inner-circle fill radius — same square-root scaling.
  const miskCoreFillRadius = pctToMiskCoreFillRadius(displayedFills['Misk Core']);

  // Misk Core title/subtitle colour and shadow, interpolated from the
  // current Misk Core fill value. At 0% the title is dark green and the
  // shadow is absent (text legible against the white-ish base); at 100%
  // the title is white and the shadow is strong (text legible against
  // the green fill); intermediate values fade smoothly between them.
  const miskCorePct = displayedFills['Misk Core'];
  const titleColor = interpolateMiskCoreTitleColor(miskCorePct);
  const subtitleColor = interpolateMiskCoreSubtitleColor(miskCorePct);
  const titleShadowOpacity = interpolateMiskCoreShadowOpacity(miskCorePct);

  return (
    <div className="quadrant-hologram-wrapper">
      {/*
        Scoped CSS for the fill animations. Inline so this chunk doesn't
        touch QuadrantCircle.css. The transitions apply to SVG circle's
        `r` attribute, which all evergreen browsers (Chrome/Edge/Safari
        and Firefox 88+) support. Older browsers degrade gracefully —
        the value snaps to target instead of animating.

        The title-text fill transition keeps the title colour change
        synchronised with the fill animation (same 1.5s duration).
      */}
      <style>{`
        .fill-clip-circle {
          transition: r 1.5s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        }
        .misk-core-fill {
          transition: r 1.5s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        }
        .misk-core-title-tspan {
          transition: fill 1.5s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        }
      `}</style>

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

            {/* Per-quadrant radial clipPaths. r is driven by displayedFills. */}
            <clipPath id="fillClipAcademic">
              <circle className="fill-clip-circle" cx="250" cy="250" r={clipRadiusFor('Academic')} />
            </clipPath>
            <clipPath id="fillClipInternship">
              <circle className="fill-clip-circle" cx="250" cy="250" r={clipRadiusFor('Internship')} />
            </clipPath>
            <clipPath id="fillClipIdentity">
              <circle className="fill-clip-circle" cx="250" cy="250" r={clipRadiusFor('National Identity')} />
            </clipPath>
            <clipPath id="fillClipLeadership">
              <circle className="fill-clip-circle" cx="250" cy="250" r={clipRadiusFor('Leadership')} />
            </clipPath>

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

          {/*
            ===========================================================
            QUADRANT SLICES — outline + filled-and-clipped layers.
            ===========================================================
          */}

          {/* TOP-RIGHT: Internship */}
          <path
            d="M 250 250 L 250 60 A 190 190 0 0 1 440 250 Z"
            fill="none"
            stroke={SEG_TOP_RIGHT.color}
            strokeWidth="2"
            opacity="0.45"
            pointerEvents="none"
          />
          <path
            d="M 250 250 L 250 60 A 190 190 0 0 1 440 250 Z"
            fill="url(#internshipGrad)"
            filter="url(#glow)"
            clipPath="url(#fillClipInternship)"
            className="quadrant-segment"
            onMouseEnter={() => setHoveredQuadrant(SEG_TOP_RIGHT)}
            onMouseLeave={() => setHoveredQuadrant(null)}
          />

          {/* BOTTOM-RIGHT: National Identity */}
          <path
            d="M 250 250 L 440 250 A 190 190 0 0 1 250 440 Z"
            fill="none"
            stroke={SEG_BOTTOM_RIGHT.color}
            strokeWidth="2"
            opacity="0.45"
            pointerEvents="none"
          />
          <path
            d="M 250 250 L 440 250 A 190 190 0 0 1 250 440 Z"
            fill="url(#identityGrad)"
            filter="url(#glow)"
            clipPath="url(#fillClipIdentity)"
            className="quadrant-segment"
            onMouseEnter={() => setHoveredQuadrant(SEG_BOTTOM_RIGHT)}
            onMouseLeave={() => setHoveredQuadrant(null)}
          />

          {/* BOTTOM-LEFT: Leadership */}
          <path
            d="M 250 250 L 250 440 A 190 190 0 0 1 60 250 Z"
            fill="none"
            stroke={SEG_BOTTOM_LEFT.color}
            strokeWidth="2"
            opacity="0.45"
            pointerEvents="none"
          />
          <path
            d="M 250 250 L 250 440 A 190 190 0 0 1 60 250 Z"
            fill="url(#leadershipGrad)"
            filter="url(#glow)"
            clipPath="url(#fillClipLeadership)"
            className="quadrant-segment"
            onMouseEnter={() => setHoveredQuadrant(SEG_BOTTOM_LEFT)}
            onMouseLeave={() => setHoveredQuadrant(null)}
          />

          {/* TOP-LEFT: Academic */}
          <path
            d="M 250 250 L 60 250 A 190 190 0 0 1 250 60 Z"
            fill="none"
            stroke={SEG_TOP_LEFT.color}
            strokeWidth="2"
            opacity="0.45"
            pointerEvents="none"
          />
          <path
            d="M 250 250 L 60 250 A 190 190 0 0 1 250 60 Z"
            fill="url(#academicGrad)"
            filter="url(#glow)"
            clipPath="url(#fillClipAcademic)"
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

          {/* Misk Core base — white-ish gradient surface, click target. */}
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
            aria-label={isCenterClickable ? 'Open Misk Core' : undefined}
          />

          {/* Misk Core completion fill — grows with Misk Core %. */}
          <circle
            className="misk-core-fill"
            cx="250"
            cy="250"
            r={miskCoreFillRadius}
            fill="#02664b"
            opacity="0.85"
            pointerEvents="none"
          />

          <circle cx="235" cy="235" r="55" fill="rgba(255,255,255,0.35)" pointerEvents="none" />

          {/*
            Misk Core title — colours and shadow fade with the fill so the
            text stays legible at every state.
              0% fill: dark green title, no shadow (legible on white-ish base)
            100% fill: white title, strong shadow (legible on green fill)
            Intermediate values interpolate linearly between the two.
          */}
          <text
            x="250"
            y="250"
            textAnchor="middle"
            dominantBaseline="middle"
            fontWeight="900"
            letterSpacing="0.4"
            className="misk-core-title"
            style={{
              cursor: 'pointer',
              filter: `drop-shadow(0 2px 4px rgba(0,0,0,${titleShadowOpacity.toFixed(3)}))`,
            }}
            onMouseEnter={() => setHoveredQuadrant(miskCore)}
            onMouseLeave={() => setHoveredQuadrant(null)}
            onClick={isCenterClickable ? onMiskCoreClick : undefined}
          >
            <tspan
              className="misk-core-title-tspan"
              x="250"
              dy={-(coreSubSize * 0.35)}
              fontSize={coreTitleSize}
              fill={titleColor}
            >
              Misk Core
            </tspan>
            <tspan
              className="misk-core-title-tspan"
              x="250"
              dy={coreSubSize * 1.35}
              fontSize={coreSubSize}
              fill={subtitleColor}
              opacity="0.95"
              fontWeight="800"
            >
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

// ============================================================
// Helpers — kept at module scope so they're easy to unit-test
// and don't recreate on every render.
// ============================================================

// Clamp a number-or-undefined to a sane [0, 100] range.
function clampPct(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return 0;
  if (n < 0) return 0;
  if (n > 100) return 100;
  return n;
}

// Square-root scaling so the visible *area* of a slice fill matches the
// percentage. Area of a circle scales with r², so to get fill_area/total_area
// = pct/100 we need r/R = sqrt(pct/100), i.e. r = R * sqrt(pct/100).
// MIN_R keeps a tiny invisible dot at the center even at 0% so SVG's
// clip-path layer-out stays stable; the visual outline of the empty slice
// is what the user actually sees at 0%.
function pctToClipRadius(pct) {
  const MIN_R = 5;
  const MAX_R = 190;
  const t = clampPct(pct) / 100;
  return MIN_R + (MAX_R - MIN_R) * Math.sqrt(t);
}

// Misk Core inner disk — same square-root area scaling, but starts at
// radius 0 (a fully-empty disk is invisible, which is what we want).
function pctToMiskCoreFillRadius(pct) {
  const MAX_R = 90;
  const t = clampPct(pct) / 100;
  return MAX_R * Math.sqrt(t);
}

// Linear interpolation between two hex colours, expressed in 0..1 t.
// Returns 'rgb(r, g, b)' so SVG fill accepts it directly.
function lerpHex(hexA, hexB, t) {
  const tt = Math.max(0, Math.min(1, t));
  const a = hexToRgb(hexA);
  const b = hexToRgb(hexB);
  const r = Math.round(a.r + (b.r - a.r) * tt);
  const g = Math.round(a.g + (b.g - a.g) * tt);
  const bl = Math.round(a.b + (b.b - a.b) * tt);
  return `rgb(${r}, ${g}, ${bl})`;
}

function hexToRgb(hex) {
  // Tolerates leading #. Assumes 6-digit hex; this is a single internal
  // helper so we don't bother with 3-digit shorthand.
  const cleaned = hex.replace(/^#/, '');
  return {
    r: parseInt(cleaned.slice(0, 2), 16),
    g: parseInt(cleaned.slice(2, 4), 16),
    b: parseInt(cleaned.slice(4, 6), 16),
  };
}

// Misk Core title colour at a given fill %:
//   0%  -> dark green #02664b (legible on white-ish empty base)
//   100% -> white #ffffff (legible on green fill)
// Linear in the 0..100 range. No special-case thresholds; smooth fade.
function interpolateMiskCoreTitleColor(pct) {
  const t = clampPct(pct) / 100;
  return lerpHex('#02664b', '#ffffff', t);
}

// Subtitle colour — slightly lighter green at 0%, pale green at 100% so
// the subtitle stays visually subordinate to the title at every state
// rather than competing with white-on-green.
function interpolateMiskCoreSubtitleColor(pct) {
  const t = clampPct(pct) / 100;
  return lerpHex('#0a5c49', '#e6fff6', t);
}

// Title drop-shadow opacity: absent at 0% (no shadow needed on a light
// background under dark text), strong at 100% (lifts white text off
// the green fill). Linear across the range.
function interpolateMiskCoreShadowOpacity(pct) {
  const t = clampPct(pct) / 100;
  const MIN_OPACITY = 0.0;
  const MAX_OPACITY = 0.55;
  return MIN_OPACITY + (MAX_OPACITY - MIN_OPACITY) * t;
}

export default QuadrantCircle3D;