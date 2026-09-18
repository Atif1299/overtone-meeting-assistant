import { Link } from "react-router-dom";
import { seller } from "../legal.js";

export default function ContactPage() {
  return (
    <article className="legal-page">
      <header className="legal-header">
        <p className="eyebrow">Company</p>
        <h1>Contact</h1>
        <p className="legal-updated">We read every message.</p>
      </header>

      <section className="legal-section">
        <h2>Email</h2>
        <p>
          <a href={`mailto:${seller.email}`}>{seller.email}</a>
        </p>
        <p>
          Use this for product questions, privacy requests, and billing issues we can help route to Paddle.
        </p>
      </section>

      <section className="legal-section">
        <h2>Operator</h2>
        <p>
          {seller.legalName}, trading as {seller.tradingName}<br />
          {seller.addressLine}
        </p>
      </section>

      <section className="legal-section">
        <h2>Policies</h2>
        <p>
          <Link to="/terms">Terms of Service</Link>
          <br />
          <Link to="/privacy">Privacy Policy</Link>
          <br />
          <Link to="/refund">Refund Policy</Link>
        </p>
      </section>
    </article>
  );
}
