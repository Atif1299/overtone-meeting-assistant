import { Link } from "react-router-dom";
import { dashboardUrl } from "../../config.js";
import BrandLogo from "../visuals/BrandLogo.jsx";
import { integrations } from "../visuals/integrations.js";

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

const footerPlatforms = integrations.filter((i) =>
  ["googlemeet", "zoom", "microsoftteams"].includes(i.id)
);

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
        <div className="footer-social footer-social--logos">
          {footerPlatforms.map((brand) => (
            <span key={brand.id} className="footer-platform" title={brand.label}>
              <BrandLogo brand={brand} size={20} />
            </span>
          ))}
        </div>
      </div>
    </footer>
  );
}
