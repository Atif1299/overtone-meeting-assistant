import { Link } from "react-router-dom";
import { dashboardUrl } from "../../config.js";
import { platforms } from "../visuals/platforms.js";
import PlatformLogo from "../visuals/PlatformLogo.jsx";

const columns = [
  {
    title: "Product",
    links: [
      { to: "/features", label: "Features" },
      { to: "/pricing", label: "Pricing" },
      { to: "/how-it-works", label: "How it works" },
      { to: "/use-cases", label: "Use cases" },
    ],
  },
  {
    title: "Resources",
    links: [
      { href: `${dashboardUrl}/signup`, label: "Start free trial", external: true },
      { href: `${dashboardUrl}/login`, label: "Sign in", external: true },
      { to: "/how-it-works", label: "Getting started" },
    ],
  },
  {
    title: "Company",
    links: [
      { to: "/use-cases", label: "Customers" },
      { to: "/features", label: "Platform" },
    ],
  },
  {
    title: "Legal",
    links: [
      { to: "/privacy", label: "Privacy" },
      { to: "/terms", label: "Terms" },
    ],
  },
];

export default function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="footer-grid">
        <div className="footer-brand">
          <p className="footer-logo"><span className="logo-mark">▲</span> Overtone</p>
          <p className="footer-tagline">
            AI presentation agent for live meetings. Upload a deck, join the call, present and answer — grounded in your slides.
          </p>
        </div>
        {columns.map((col) => (
          <div key={col.title} className="footer-col">
            <p className="footer-col-title">{col.title}</p>
            <ul>
              {col.links.map((link) => (
                <li key={link.label}>
                  {link.external ? (
                    <a href={link.href}>{link.label}</a>
                  ) : (
                    <Link to={link.to}>{link.label}</Link>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="footer-bottom">
        <p>© {new Date().getFullYear()} Overtone. All rights reserved.</p>
        <div className="footer-social">
          {platforms.slice(0, 3).map((p) => (
            <PlatformLogo key={p.id} platform={p} size="sm" />
          ))}
        </div>
      </div>
    </footer>
  );
}
