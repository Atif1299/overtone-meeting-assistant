import { useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { Menu, X } from "lucide-react";
import { dashboardUrl, navLinks } from "../../config.js";
import MobileNav from "./MobileNav.jsx";

export default function SiteHeader() {
  const [open, setOpen] = useState(false);

  return (
    <header className={`site-header${open ? " is-menu-open" : ""}`}>
      <Link to="/" className="logo" onClick={() => setOpen(false)}>
        <span className="logo-mark">▲</span> Overtone
      </Link>

      <nav className="site-nav desktop-only" aria-label="Primary">
        {navLinks.map((item) => (
          <NavLink key={item.to} to={item.to}>
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="header-cta desktop-only">
        <a href={`${dashboardUrl}/login`} className="btn btn-ghost">
          Sign in
        </a>
        <a href={`${dashboardUrl}/signup`} className="btn btn-primary">
          Start free trial
        </a>
      </div>

      <button
        type="button"
        className="mobile-menu-btn mobile-only"
        aria-label={open ? "Close menu" : "Open menu"}
        aria-expanded={open}
        aria-controls="mobile-nav-panel"
        onClick={() => setOpen((current) => !current)}
      >
        {open ? <X size={22} strokeWidth={2} /> : <Menu size={22} strokeWidth={2} />}
      </button>

      <MobileNav open={open} onClose={() => setOpen(false)} />
    </header>
  );
}
