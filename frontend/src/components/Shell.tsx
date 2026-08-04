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
        Universidad del Rosario · ConvocaUR
      </footer>
    </div>
  );
}
