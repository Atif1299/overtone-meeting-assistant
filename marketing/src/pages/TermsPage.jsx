import { Link } from "react-router-dom";
import { paddleLinks, seller } from "../legal.js";

export default function TermsPage() {
  return (
    <article className="legal-page">
      <header className="legal-header">
        <p className="eyebrow">Legal</p>
        <h1>Terms of Service</h1>
        <p className="legal-updated">Last updated: 19 September 2026</p>
      </header>

      <section className="legal-section">
        <h2>Who you contract with</h2>
        <p>
          These Terms are an agreement between you and {seller.legalName}, trading as {seller.tradingName}
          (“DeckVoice”, “we”, “us”). By accessing or using DeckVoice, you agree to these Terms. If you do not
          agree, do not use the service.
        </p>
      </section>

      <section className="legal-section">
        <h2>Service description</h2>
        <p>
          DeckVoice is a software-as-a-service product: an AI meeting presentation agent that indexes presentation
          files, joins video meetings via third-party bots, and answers audience questions using indexed content.
          Plans include Free, Starter, and Pro, with monthly limits on bot launches and deck uploads as shown on
          the <Link to="/pricing">Pricing</Link> page.
        </p>
      </section>

      <section className="legal-section">
        <h2>Merchant of record</h2>
        <p>
          Payment processing for paid DeckVoice subscriptions is provided by Paddle.com Market Ltd and its
          affiliates (“Paddle”). Paddle is the Merchant of Record for these purchases. Paddle handles checkout,
          invoicing, sales tax, and buyer payment support. Your purchase is also subject to{" "}
          <a href={paddleLinks.buyerTerms} target="_blank" rel="noreferrer">Paddle’s Buyer Terms</a>.
        </p>
      </section>

      <section className="legal-section">
        <h2>Subscriptions, fees, and cancellation</h2>
        <p>
          Paid plans bill monthly in USD until you cancel. You may cancel at any time from the DeckVoice billing
          page or the Paddle customer portal. Cancellation stops future renewals; you keep access until the end of
          the paid period unless a refund applies. Taxes, payment methods, receipts, and related billing terms are
          governed by <a href={paddleLinks.buyerTerms} target="_blank" rel="noreferrer">Paddle’s Buyer Terms</a>.
          Refunds are described in our <Link to="/refund">Refund Policy</Link>.
        </p>
      </section>

      <section className="legal-section">
        <h2>Acceptable use</h2>
        <p>You must not misuse DeckVoice. That includes, at minimum:</p>
        <ul>
          <li>unlawful use, including violating meeting-platform rules (Google Meet, Zoom, Microsoft Teams);</li>
          <li>fraud, spam, or deceptive activity;</li>
          <li>infringing intellectual property or uploading content you do not have rights to present;</li>
          <li>interfering with security, including malware, probing, scraping, or attempting to bypass usage limits.</li>
        </ul>
        <p>You are responsible for content you upload and for how the agent is used in meetings you launch.</p>
      </section>

      <section className="legal-section">
        <h2>Intellectual property</h2>
        <p>
          DeckVoice retains all rights in the service, software, documentation, and branding. You retain rights in
          decks and other content you upload. You grant us a limited licence to host, index, and present that
          content solely to operate the service for you.
        </p>
      </section>

      <section className="legal-section">
        <h2>Service level</h2>
        <p>
          The service is provided “as is”. We do not guarantee uninterrupted, timely, or error-free performance.
          AI-generated speech and answers are grounded in uploaded content but can be incomplete; review them before
          relying on them in high-stakes meetings.
        </p>
      </section>

      <section className="legal-section">
        <h2>Suspension and termination</h2>
        <p>
          We may suspend or terminate access for material breach of these Terms, non-payment, security or fraud
          risk, or repeated or serious policy violations. You may stop using the service at any time and request
          account deletion via the contact details below.
        </p>
      </section>

      <section className="legal-section">
        <h2>Contact</h2>
        <p>
          {seller.legalName}, trading as {seller.tradingName}<br />
          {seller.addressLine}<br />
          Email: <a href={`mailto:${seller.email}`}>{seller.email}</a>
        </p>
        <p>
          See also <Link to="/privacy">Privacy</Link>, <Link to="/refund">Refunds</Link>, and{" "}
          <Link to="/contact">Contact</Link>.
        </p>
      </section>
    </article>
  );
}
