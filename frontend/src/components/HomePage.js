import React from 'react';
import { Link } from 'react-router-dom';
import QuadrantCircle3D from './QuadrantCircle3D';
import './HomePage.css';

// Header logo only (no big center watermark)
import miskLogo from '../assets/misk-logo.png';

import {
  BookOpen,
  Pencil,
  FileText,
  Target,
  Lightbulb,
  Microscope,
  Star,
  Ruler,
  Trophy,
  Palette,
  Telescope,
  GraduationCap,
  Laptop,
  Globe,
  FlaskConical,
  Book,
  FlaskRound,
} from 'lucide-react';

const HomePage = () => {
  return (
    <div className="home-page">
      {/* ✅ Lucide-only background icons */}
      <div className="education-background-full" aria-hidden="true">
        <div className="floating-icon" style={{ top: '10%', left: '8%', animationDelay: '0s' }}>
          <BookOpen className="bg-icon" size={46} />
        </div>
        <div className="floating-icon" style={{ top: '14%', right: '10%', animationDelay: '2s' }}>
          <Pencil className="bg-icon" size={44} />
        </div>
        <div className="floating-icon" style={{ bottom: '12%', left: '10%', animationDelay: '4s' }}>
          <FileText className="bg-icon" size={46} />
        </div>
        <div className="floating-icon" style={{ top: '45%', left: '4%', animationDelay: '1s' }}>
          <Target className="bg-icon" size={44} />
        </div>
        <div className="floating-icon" style={{ top: '22%', right: '18%', animationDelay: '3s' }}>
          <Lightbulb className="bg-icon" size={44} />
        </div>
        <div className="floating-icon" style={{ top: '40%', right: '6%', animationDelay: '2.5s' }}>
          <Microscope className="bg-icon" size={46} />
        </div>
        <div className="floating-icon" style={{ bottom: '28%', left: '16%', animationDelay: '4.5s' }}>
          <Star className="bg-icon" size={42} />
        </div>
        <div className="floating-icon" style={{ top: '28%', left: '14%', animationDelay: '1.5s' }}>
          <Ruler className="bg-icon" size={42} />
        </div>
        <div className="floating-icon" style={{ bottom: '26%', right: '12%', animationDelay: '3.5s' }}>
          <Trophy className="bg-icon" size={44} />
        </div>
        <div className="floating-icon" style={{ top: '60%', left: '10%', animationDelay: '2s' }}>
          <Palette className="bg-icon" size={44} />
        </div>
        <div className="floating-icon" style={{ top: '66%', right: '16%', animationDelay: '4s' }}>
          <Telescope className="bg-icon" size={46} />
        </div>
        <div className="floating-icon" style={{ top: '34%', left: '24%', animationDelay: '3s' }}>
          <GraduationCap className="bg-icon" size={44} />
        </div>
        <div className="floating-icon" style={{ bottom: '36%', right: '7%', animationDelay: '1.8s' }}>
          <Laptop className="bg-icon" size={44} />
        </div>
        <div className="floating-icon" style={{ top: '58%', right: '26%', animationDelay: '2.3s' }}>
          <Globe className="bg-icon" size={44} />
        </div>
        <div className="floating-icon" style={{ bottom: '44%', left: '22%', animationDelay: '4.2s' }}>
          <FlaskConical className="bg-icon" size={44} />
        </div>
        <div className="floating-icon" style={{ top: '42%', right: '28%', animationDelay: '1.2s' }}>
          <Book className="bg-icon" size={44} />
        </div>
        <div className="floating-icon" style={{ bottom: '52%', right: '4%', animationDelay: '3.8s' }}>
          <FlaskRound className="bg-icon" size={46} />
        </div>
      </div>

      <header className="header">
        <div className="container">
          <div className="header-content header-content--left">
            {/* ✅ Much bigger brand block (within banner) */}
            <div className="brand brand--xl">
              <img className="brand-logo brand-logo--xl" src={miskLogo} alt="MISK Schools" />
              <div className="brand-text-wrap">
                <div className="brand-text brand-text--xl">MISK SCHOOLS</div>
                <div className="brand-subtext">DIPLOMA</div>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="hero">
        <div className="container">
          <h1>MISK Diploma Tracker</h1>
          <p>Track your journey to excellence</p>

          <div className="canvas-container canvas-container--large">
            <QuadrantCircle3D size={620} />
          </div>

          <div className="button-container">
            <Link to="/login?role=student" className="btn btn-primary">
              Student Login
            </Link>
            <Link to="/login?role=teacher" className="btn btn-secondary">
              Teacher Login
            </Link>
          </div>
        </div>
      </main>

      <footer className="footer">
        <div className="container">
          <p>© 2025 MISK Schools. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
};

export default HomePage;
