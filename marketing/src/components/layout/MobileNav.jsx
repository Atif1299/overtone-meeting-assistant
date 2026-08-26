import { NavLink } from "react-router-dom";
import { dashboardUrl, navLinks } from "../../config.js";

export default function MobileNav({ open, onClose }) {
  if (!open) return null;

  return (
    <div className="mobile-nav-overlay" role="dialog" aria-modal="true">
      <div className="mobile-nav-panel">
        <button type="button" className="mobile-nav-close" onClick={onClose} aria-label="Close menu">
          ✕
        </button>
        <nav className="mobile-nav-links">
          {navLinks.map((item) => (
            <NavLink key={item.to} to={item.to} onClick={onClose}>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="mobile-nav-cta">
          <a href={`${dashboardUrl}/login`} className="btn btn-ghost" onClick={onClose}>Sign in</a>
          <a href={`${dashboardUrl}/signup`} className="btn btn-primary" onClick={onClose}>Start free trial</a>
        </div>
      </div>
    </div>
  );
}
