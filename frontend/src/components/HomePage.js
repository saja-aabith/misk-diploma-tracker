import React from 'react';
import { Link } from 'react-router-dom';
import QuadrantCircle3D from './QuadrantCircle3D';
import './HomePage.css';

function HomePage() {
  return (
    <div className="home-page">
      {/* Animated educational background across entire page */}
      <div className="education-background-full">
        <div className="floating-icon" style={{ top: '8%', left: '10%', animationDelay: '0s' }}>📚</div>
        <div className="floating-icon" style={{ top: '15%', right: '8%', animationDelay: '2s' }}>✏️</div>
        <div className="floating-icon" style={{ bottom: '12%', left: '8%', animationDelay: '4s' }}>📝</div>
        <div className="floating-icon" style={{ top: '45%', left: '5%', animationDelay: '1s' }}>🎯</div>
        <div className="floating-icon" style={{ top: '12%', right: '15%', animationDelay: '3s' }}>💡</div>
        <div className="floating-icon" style={{ bottom: '18%', right: '12%', animationDelay: '5s' }}>📊</div>
        <div className="floating-icon" style={{ top: '35%', right: '6%', animationDelay: '2.5s' }}>🔬</div>
        <div className="floating-icon" style={{ bottom: '25%', left: '10%', animationDelay: '4.5s' }}>🌟</div>
        <div className="floating-icon" style={{ top: '22%', left: '6%', animationDelay: '1.5s' }}>📐</div>
        <div className="floating-icon" style={{ bottom: '22%', right: '10%', animationDelay: '3.5s' }}>🏆</div>
        <div className="floating-icon" style={{ top: '55%', left: '15%', animationDelay: '2s' }}>🎨</div>
        <div className="floating-icon" style={{ top: '65%', right: '15%', animationDelay: '4s' }}>🔭</div>
        <div className="floating-icon" style={{ top: '30%', left: '12%', animationDelay: '3s' }}>🎓</div>
        <div className="floating-icon" style={{ bottom: '35%', right: '8%', animationDelay: '1.8s' }}>💻</div>
        <div className="floating-icon" style={{ top: '60%', right: '20%', animationDelay: '2.3s' }}>🌍</div>
        <div className="floating-icon" style={{ bottom: '40%', left: '18%', animationDelay: '4.2s' }}>⚗️</div>
        <div className="floating-icon" style={{ top: '40%', right: '25%', animationDelay: '1.2s' }}>📖</div>
        <div className="floating-icon" style={{ bottom: '50%', right: '5%', animationDelay: '3.8s' }}>🧪</div>
      </div>

      <header className="header">
        <div className="container">
          <div className="header-content">
            <div className="logo">MISK Schools</div>
          </div>
        </div>
      </header>

      <main className="hero">
        <div className="container">
          <h1>MISK Diploma Tracker</h1>
          <p>Track your journey across four pillars of excellence</p>
          
          <div className="canvas-container">
            <QuadrantCircle3D size={500} />
          </div>

          <div className="button-container">
            <Link to="/login?role=student" className="btn btn-primary">
              <span className="btn-icon"></span>
              Student Login
            </Link>
            <Link to="/login?role=teacher" className="btn btn-secondary">
              <span className="btn-icon"></span>
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
}

export default HomePage;