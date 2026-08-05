import { NavLink } from "react-router-dom";
import type { ReactNode } from "react";

export function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="shell">
      <header className="nav">
        <NavLink to="/" className="brand">
          Convoca<em>UR</em>
        </NavLink>
        <nav className="nav-links">
          <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : undefined)}>
            Inicio
          </NavLink>
          <NavLink to="/secop" className={({ isActive }) => (isActive ? "active" : undefined)}>
            SECOP
          </NavLink>
          <NavLink to="/matching" className={({ isActive }) => (isActive ? "active" : undefined)}>
            Matching
          </NavLink>
        </nav>
      </header>
      <main className="main">{children}</main>
      <footer className="footer">
        <div className="footer-inner">
          <div className="footer-copy">
            <strong>ConvocaUR</strong>
            <span>Universidad del Rosario · Minciencias · SECOP CTeI</span>
          </div>
          <div className="footer-logos" aria-label="Instituciones">
            <a
              className="footer-logo"
              href="https://www.urosario.edu.co"
              target="_blank"
              rel="noreferrer"
              title="Universidad del Rosario"
            >
              <img
                className="logo-urosario"
                src="/brand/urosario-clear.png"
                alt="Universidad del Rosario"
              />
            </a>
            <span className="footer-logo-sep" aria-hidden="true" />
            <a
              className="footer-logo"
              href="https://minciencias.gov.co"
              target="_blank"
              rel="noreferrer"
              title="Minciencias"
            >
              <img src="/brand/minciencias-clear.png" alt="Minciencias" />
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
