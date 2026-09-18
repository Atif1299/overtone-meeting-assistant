import { Link } from "react-router-dom";
import { paddleLinks, seller } from "../legal.js";

export default function PrivacyPage() {
  return (
    <article className="legal-page">
      <header className="legal-header">
        <p className="eyebrow">Legal</p>
        <h1>Privacy Policy</h1>
        <p className="legal-updated">Last updated: 19 September 2026</p>
      </header>

      <section className="legal-section">
        <h2>Who we are</h2>
        <p>
          {seller.legalName}, trading as {seller.tradingName} (“DeckVoice”, “we”, “us”), is the controller for
          personal data we collect about users of our product and website. Principal place of business:{" "}
          {seller.addressLine}. Privacy contact: <a href={`mailto:${seller.email}`}>{seller.email}</a>.
        </p>
      </section>

      <section className="legal-section">
        <h2>What we collect</h2>
        <ul>
          <li>Account data: name, email, login credentials (via Supabase Auth).</li>
          <li>Workspace content: presentation files you upload and related slide index data.</li>
          <li>Session data: meeting URLs you submit, bot IDs, transcripts, and session status.</li>
          <li>Usage and device data: IP address, browser type, and product telemetry needed to run quotas and debug failures.</li>
          <li>Support messages you send to us.</li>
        </ul>
        <p>
          Payment card data is collected by Paddle as an independent controller when you subscribe. We do not store
          card numbers. See <a href={paddleLinks.privacy} target="_blank" rel="noreferrer">Paddle’s privacy policy</a>.
        </p>
      </section>

      <section className="legal-section">
        <h2>Why we use it</h2>
        <ul>
          <li>To create accounts and provide the service (contract).</li>
          <li>To index decks, launch meeting bots, run live presentation and Q&amp;A, and enforce plan limits (contract).</li>
          <li>To keep the service secure and prevent fraud or abuse (legitimate interests).</li>
          <li>To improve reliability and fix bugs (legitimate interests).</li>
          <li>To respond to support requests (contract / legitimate interests).</li>
          <li>To meet legal obligations, including responding to lawful requests.</li>
        </ul>
        <p>We do not sell your personal data. We do not send marketing emails unless you ask us to.</p>
      </section>

      <section className="legal-section">
        <h2>Who we share it with</h2>
        <ul>
          <li>Hosting and infrastructure providers (Google Cloud, database hosting).</li>
          <li>Authentication (Supabase).</li>
          <li>Meeting capture (Recall.ai) for bots you launch.</li>
          <li>AI processing (Google Gemini) for live speech and grounded answers.</li>
          <li>
            Paddle, as merchant of record, for checkout, subscriptions, tax, and invoicing.
          </li>
          <li>Professional advisers and authorities where required by law or to protect rights and safety.</li>
        </ul>
      </section>

      <section className="legal-section">
        <h2>International transfers</h2>
        <p>
          We operate from Pakistan. Infrastructure and processors may store or process data in the United States and
          other countries (including Google Cloud in us-central1). Where required, we rely on contractual safeguards
          such as standard contractual clauses with those providers.
        </p>
      </section>

      <section className="legal-section">
        <h2>Retention</h2>
        <p>
          Account, workspace, and session data are kept while your account is active. You may delete presentations
          from the dashboard. After account deletion we delete or anonymize personal data within 30 days unless a
          longer period is required for legal, tax, or security records. Billing records held by Paddle follow
          Paddle’s retention rules.
        </p>
      </section>

      <section className="legal-section">
        <h2>Your rights</h2>
        <p>
          You may request access, correction, deletion, restriction, portability, or objection, and you may withdraw
          consent where processing is based on consent. Email <a href={`mailto:${seller.email}`}>{seller.email}</a>.
          We aim to respond within one month. You may also complain to your local data protection authority.
        </p>
      </section>

      <section className="legal-section">
        <h2>Security</h2>
        <p>
          We use HTTPS, access controls, and encrypted storage in transit. No method of transmission is completely
          secure; we take reasonable technical and organisational measures appropriate to a SaaS product of this size.
        </p>
      </section>

      <section className="legal-section">
        <h2>Cookies</h2>
        <p>
          The marketing site uses essential cookies or local storage only as needed to load the site. The dashboard
          uses essential cookies for sign-in and session security. We do not use advertising cookies. You can block
          cookies in your browser; essential cookies are required for the dashboard to work.
        </p>
      </section>

      <section className="legal-section">
        <h2>Contact</h2>
        <p>
          {seller.legalName}, trading as {seller.tradingName}<br />
          {seller.addressLine}<br />
          <a href={`mailto:${seller.email}`}>{seller.email}</a>
        </p>
        <p>
          Related: <Link to="/terms">Terms</Link>, <Link to="/refund">Refunds</Link>,{" "}
          <Link to="/contact">Contact</Link>.
        </p>
      </section>
    </article>
  );
}
