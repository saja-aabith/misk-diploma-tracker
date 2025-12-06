import React from 'react';
import { Link } from 'react-router-dom';
import QuadrantCircle3D from './QuadrantCircle3D';

function HomePage() {
  return (
    <div className="home-page">
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
            <QuadrantCircle3D size={300} />
          </div>

          <div className="button-group">
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
}

export default HomePage;