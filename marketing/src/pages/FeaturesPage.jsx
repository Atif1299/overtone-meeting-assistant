import { dashboardUrl } from "../config.js";
import { media } from "../components/visuals/media.js";
import HeroSection from "../components/sections/HeroSection.jsx";
import FeatureGrid from "../components/sections/FeatureGrid.jsx";
import SplitFeature from "../components/sections/SplitFeature.jsx";
import IntegrationStrip from "../components/sections/IntegrationStrip.jsx";
import FAQAccordion from "../components/sections/FAQAccordion.jsx";
import CTABand from "../components/sections/CTABand.jsx";

const capabilities = [
  { icon: "▣", title: "Deck ingestion", body: "Upload PPTX or PDF. Vision indexes every slide into searchable chunks.", image: media.uploadIndex },
  { icon: "▶", title: "Bot launch", body: "One-click Recall.ai bot join with presenter output media as camera.", image: media.botMeeting },
  { icon: "◍", title: "Live sessions", body: "Monitor bot state, transcript queue, and session health in real time.", image: media.voiceLive },
  { icon: "◆", title: "Agent studio", body: "Version prompt instructions per workspace. Activate the tone that fits your brand.", image: media.agentStudio },
  { icon: "◈", title: "Usage & billing", body: "Stripe subscriptions with monthly launch and upload quotas by plan.", image: media.billing },
  { icon: "◉", title: "Multi-tenant SaaS", body: "Isolated workspaces, Supabase auth, and per-tenant presentation catalogs.", image: media.workspace },
];

const featuresFaq = [
  { q: "Can I use my existing sales deck?", a: "Yes. Upload PPTX or PDF — Overtone indexes every slide and uses that content for live Q&A." },
  { q: "Does the bot appear as a separate app?", a: "No. Recall carries your presenter webpage as the bot's camera output — participants see your slides and hear the voice agent." },
  { q: "Can I customize the agent's tone?", a: "Yes. The Agent studio lets you version prompt instructions per workspace." },
];

export default function FeaturesPage() {
  return (
    <>
      <HeroSection
        badge="Platform"
        title="Everything to run live AI presentations"
        subtitle="From deck upload to meeting bot to grounded Q&A — one operator stack, built for production demos."
        primaryCta="Start free trial"
        primaryHref={`${dashboardUrl}/signup`}
        secondaryCta="View pricing"
        secondaryHref="/pricing"
        imageSrc={media.heroDashboard}
      />

      <FeatureGrid
        eyebrow="Capabilities"
        title="Core platform features"
        subtitle="Six pillars that make Overtone a complete presentation agent — not a chatbot with slides pasted in."
        items={capabilities}
      />

      <SplitFeature
        eyebrow="Deep dive"
        title="Upload & index — your deck becomes a knowledge base"
        body="Every slide is processed through vision models, chunked, embedded, and stored in pgvector. When the audience asks a question, the agent searches what you actually uploaded."
        bullets={["PPTX and PDF support", "Per-slide metadata extraction", "Background indexing with status tracking"]}
        imageSrc={media.uploadIndex}
        tone="dark"
      />

      <SplitFeature
        eyebrow="Deep dive"
        title="Launch & join — Recall carries your presenter as the bot camera"
        body="Paste a Google Meet, Zoom, or Teams URL. Overtone creates a Recall bot, opens the presenter webpage as output media, and connects the realtime voice relay."
        bullets={["No separate app in the meeting", "Webhook-driven session lifecycle", "Signed presenter URLs for security"]}
        imageSrc={media.botMeeting}
        tone="light"
        reverse
      />

      <SplitFeature
        eyebrow="Deep dive"
        title="Live voice & grounded answers"
        body="Gemini Live handles speech-to-speech. Tools navigate slides and search deck content — so answers stay tied to your material, not generic LLM knowledge."
        bullets={["navigate_to_slide · get_slide_details · search_and_answer", "Interruption-aware delivery", "Concise spoken responses"]}
        imageSrc={media.voiceLive}
        tone="dark"
      />

      <IntegrationStrip title="Integrates with your meeting stack" />

      <FAQAccordion title="Platform questions" items={featuresFaq} />

      <CTABand
        title="See the platform in action"
        subtitle="Create a free account and launch your first bot in minutes."
        primaryLabel="Start free trial"
        primaryHref={`${dashboardUrl}/signup`}
        secondaryLabel="How it works"
        secondaryHref="/how-it-works"
      />
    </>
  );
}
