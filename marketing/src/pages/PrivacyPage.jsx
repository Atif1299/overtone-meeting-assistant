export default function PrivacyPage() {
  return (
    <article className="legal-page">
      <header className="legal-header">
        <p className="eyebrow">Legal</p>
        <h1>Privacy Policy</h1>
        <p className="legal-updated">Last updated: August 2026</p>
      </header>

      <section className="legal-section">
        <h2>Overview</h2>
        <p>
          Overtone ("we", "our", "us") operates an AI meeting presentation platform. This policy describes how we collect, use, and protect information when you use our services.
        </p>
      </section>

      <section className="legal-section">
        <h2>Information we collect</h2>
        <p>Account information (email, name) via Supabase Auth. Presentation files you upload. Meeting session metadata (URLs, bot IDs, session state). Billing information processed by Stripe — we do not store card numbers.</p>
      </section>

      <section className="legal-section">
        <h2>How we use information</h2>
        <p>To operate the service: index your decks, launch meeting bots, provide live presentation and Q&A, enforce usage quotas, and process subscriptions. We do not sell your data to third parties.</p>
      </section>

      <section className="legal-section">
        <h2>Data retention & deletion</h2>
        <p>Presentations and session data are retained in your workspace until you delete them. Contact us to request account deletion.</p>
      </section>

      <section className="legal-section">
        <h2>Contact</h2>
        <p>For privacy requests, contact your workspace administrator or Overtone support through the dashboard.</p>
      </section>
    </article>
  );
}
