import { useEffect } from "react";
import { createPortal } from "react-dom";
import { NavLink } from "react-router-dom";
import { dashboardUrl, navLinks } from "../../config.js";

export default function MobileNav({ open, onClose }) {
  useEffect(() => {
    if (!open) return undefined;

    const onKey = (event) => {
      if (event.key === "Escape") onClose();
    };

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", onKey);

    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div className="mobile-nav-overlay" role="presentation">
      <button type="button" className="mobile-nav-backdrop" onClick={onClose} aria-label="Close menu" />
      <div className="mobile-nav-panel" id="mobile-nav-panel" role="dialog" aria-modal="true" aria-label="Site menu">
        <nav className="mobile-nav-links" aria-label="Mobile">
          {navLinks.map((item) => (
            <NavLink key={item.to} to={item.to} onClick={onClose}>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="mobile-nav-cta">
          <a href={`${dashboardUrl}/login`} className="btn btn-ghost" onClick={onClose}>
            Sign in
          </a>
          <a href={`${dashboardUrl}/signup`} className="btn btn-primary" onClick={onClose}>
            Start free trial
          </a>
        </div>
      </div>
    </div>,
    document.body
  );
}
