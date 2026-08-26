export default function PrivacyPage() {
  return (
    <section className="section prose">
      <h1>Privacy Policy</h1>
      <p>Overtone processes presentation files you upload and meeting session data required to operate the AI presenter. We do not sell your data.</p>
      <p>Uploaded decks are stored in your workspace and used solely to index slide content and serve live presentation sessions. Authentication is handled by Supabase; billing by Stripe.</p>
      <p>Contact your workspace administrator or Overtone support for data deletion requests.</p>
    </section>
  );
}
