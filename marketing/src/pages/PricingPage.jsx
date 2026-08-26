import { dashboardUrl } from "../config.js";
import { media } from "../components/visuals/media.js";
import HeroSection from "../components/sections/HeroSection.jsx";
import PricingCards from "../components/sections/PricingCards.jsx";
import ComparisonTable from "../components/sections/ComparisonTable.jsx";
import FAQAccordion from "../components/sections/FAQAccordion.jsx";
import SplitFeature from "../components/sections/SplitFeature.jsx";
import TestimonialRow from "../components/sections/TestimonialRow.jsx";
import CTABand from "../components/sections/CTABand.jsx";

const plans = [
  { name: "Free trial", price: "$0", features: ["1 bot launch / month", "1 deck upload / month", "Full presenter experience", "Community support"], cta: "Start free" },
  { name: "Starter", price: "$10", period: "/mo", features: ["5 bot launches / month", "3 deck uploads / month", "Agent prompt studio", "Email support"], cta: "Get Starter", plan: "starter" },
  { name: "Pro", price: "$20", period: "/mo", features: ["20 bot launches / month", "10 deck uploads / month", "Priority support", "Best for high-volume demos"], cta: "Get Pro", plan: "pro", featured: true },
];

const compareRows = [
  { feature: "Bot launches / month", values: ["1", "5", "20"] },
  { feature: "Deck uploads / month", values: ["1", "3", "10"] },
  { feature: "Agent prompt studio", values: ["✓", "✓", "✓"] },
  { feature: "Stripe billing portal", values: ["—", "✓", "✓"] },
  { feature: "Support", values: ["Community", "Email", "Priority"] },
];

const faq = [
  { q: "What counts as a bot launch?", a: "Each time you click Launch and Overtone creates a new Recall bot for a meeting URL, that counts as one launch for the billing period." },
  { q: "What counts as a deck upload?", a: "Each new PPTX or PDF you upload to your workspace counts as one upload, regardless of slide count." },
  { q: "Can I upgrade mid-month?", a: "Yes. Upgrade through the billing page — Stripe prorates your subscription automatically." },
  { q: "Is there a contract or lock-in?", a: "No. Cancel anytime from the Stripe customer portal. Your workspace data remains until you delete it." },
];

export default function PricingPage() {
  return (
    <>
      <HeroSection
        badge="Pricing"
        title="Simple plans that grow with your demo volume"
        subtitle="Start free. Upgrade when you need more launches and uploads. No sales call required."
        primaryCta="Start free trial"
        primaryHref={`${dashboardUrl}/signup`}
        imageSrc={media.heroDashboard}
      />

      <PricingCards plans={plans} />

      <ComparisonTable rows={compareRows} />

      <FAQAccordion title="Pricing questions" items={faq} />

      <SplitFeature
        eyebrow="Trust"
        title="Secure billing through Stripe"
        body="Payments are handled by Stripe. Manage your subscription, invoices, and payment methods from the dashboard billing page. We never store card details on our servers."
        bullets={["Stripe Checkout for upgrades", "Customer portal for plan changes", "Usage meters reset monthly"]}
        tone="dark"
        reverse
      />

      <TestimonialRow
        title="Teams upgrading when demo volume picks up"
        items={[
          { quote: "We hit the free launch limit in week one. Starter paid for itself on the first extra demo we didn't have to staff.", name: "Sam T.", role: "Sales Ops, Series B" },
          { quote: "Pro tier handles our weekly investor updates without thinking about quotas.", name: "Morgan L.", role: "CEO, Seed startup" },
        ]}
      />

      <CTABand
        title="Start presenting for free today"
        subtitle="1 launch and 1 upload included — no credit card on signup."
        primaryLabel="Create free account"
        primaryHref={`${dashboardUrl}/signup`}
        secondaryLabel="See use cases"
        secondaryHref="/use-cases"
      />
    </>
  );
}
