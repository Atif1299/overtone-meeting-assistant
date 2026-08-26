export default function TermsPage() {
  return (
    <article className="legal-page">
      <header className="legal-header">
        <p className="eyebrow">Legal</p>
        <h1>Terms of Service</h1>
        <p className="legal-updated">Last updated: August 2026</p>
      </header>

      <section className="legal-section">
        <h2>Acceptance</h2>
        <p>By accessing or using Overtone, you agree to these Terms. If you do not agree, do not use the service.</p>
      </section>

      <section className="legal-section">
        <h2>Service description</h2>
        <p>Overtone provides an AI meeting presentation agent that indexes presentation files, joins video meetings via third-party bots, and responds to audience questions using indexed content. The service is provided on a subscription basis with usage limits per plan.</p>
      </section>

      <section className="legal-section">
        <h2>Usage limits</h2>
        <p>Free, Starter, and Pro plans include monthly limits on bot launches and deck uploads as described on the Pricing page. Exceeding limits requires a plan upgrade. Usage resets at the start of each billing period.</p>
      </section>

      <section className="legal-section">
        <h2>Acceptable use</h2>
        <p>You agree to use Overtone in compliance with applicable laws and the terms of meeting platforms (Google Meet, Zoom, Microsoft Teams). You are responsible for content you upload and present.</p>
      </section>

      <section className="legal-section">
        <h2>Disclaimer</h2>
        <p>The service is provided "as is" during beta. We do not guarantee uninterrupted availability. AI-generated responses are grounded in uploaded content but should be reviewed for critical use cases.</p>
      </section>

      <section className="legal-section">
        <h2>Contact</h2>
        <p>Questions about these terms may be directed through the Overtone dashboard or your account administrator.</p>
      </section>
    </article>
  );
}
