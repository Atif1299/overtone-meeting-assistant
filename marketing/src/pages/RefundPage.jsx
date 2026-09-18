import { Link } from "react-router-dom";
import { paddleLinks, seller } from "../legal.js";

export default function RefundPage() {
  return (
    <article className="legal-page">
      <header className="legal-header">
        <p className="eyebrow">Legal</p>
        <h1>Refund Policy</h1>
        <p className="legal-updated">Last updated: 19 September 2026</p>
      </header>

      <section className="legal-section">
        <h2>Overview</h2>
        <p>
          Paid DeckVoice subscriptions are sold by Paddle as merchant of record. This policy explains when you can
          request a refund and how to do it. It does not say that all sales are final.
        </p>
      </section>

      <section className="legal-section">
        <h2>Refund period</h2>
        <p>
          You may request a refund within <strong>14 days</strong> of the original paid charge if you change your
          mind or the service did not work as described. The window is 14 days (not more than 90 days).
        </p>
      </section>

      <section className="legal-section">
        <h2>How to request a refund</h2>
        <p>
          Request refunds from Paddle at{" "}
          <a href={paddleLinks.refundRequests} target="_blank" rel="noreferrer">paddle.net</a> using the email on
          your purchase receipt. You may also email <a href={`mailto:${seller.email}`}>{seller.email}</a> and we
          will point Paddle at the transaction.
        </p>
        <p>
          Paddle’s own refund rules also apply:{" "}
          <a href={paddleLinks.refund} target="_blank" rel="noreferrer">paddle.com/legal/refund-policy</a>.
        </p>
      </section>

      <section className="legal-section">
        <h2>What we refund</h2>
        <ul>
          <li>Unused paid Starter or Pro subscription charges requested within 14 days.</li>
          <li>Duplicate or accidental charges.</li>
          <li>Service failure where DeckVoice could not be used after a good-faith attempt.</li>
        </ul>
        <p>
          Free-plan usage is not a paid charge and is not refunded. After a refund, paid-plan entitlements may be
          removed. Cancelling for the next period (without a refund) is done from the billing page; you keep access
          until the current period ends.
        </p>
      </section>

      <section className="legal-section">
        <h2>Timing</h2>
        <p>
          Approved refunds go back to the original payment method. Card refunds often show within 5–10 business days
          depending on your bank. Paddle issues a credit note for the adjustment.
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
          <Link to="/terms">Terms</Link> · <Link to="/privacy">Privacy</Link> · <Link to="/contact">Contact</Link>
        </p>
      </section>
    </article>
  );
}
