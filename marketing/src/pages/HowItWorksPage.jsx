import { dashboardUrl } from "../config.js";
import { media } from "../components/visuals/media.js";
import HeroSection from "../components/sections/HeroSection.jsx";
import StepsTimeline from "../components/sections/StepsTimeline.jsx";
import SplitFeature from "../components/sections/SplitFeature.jsx";
import FeatureGrid from "../components/sections/FeatureGrid.jsx";
import CTABand from "../components/sections/CTABand.jsx";
import ToneBand from "../components/sections/ToneBand.jsx";

const checklist = [
  { iconKey: "deck", title: "A deck", body: "PPTX or PDF — your sales deck, investor pitch, or onboarding guide." },
  { iconKey: "link", title: "A meeting link", body: "Google Meet, Zoom, or Microsoft Teams URL for the session." },
  { iconKey: "account", title: "An account", body: "Free signup — no credit card. Launch your first bot in minutes." },
];

export default function HowItWorksPage() {
  return (
    <>
      <ToneBand tone="dark" glow>
        <HeroSection
          badge="Workflow"
          title="From deck upload to live meeting in minutes"
          subtitle="Four steps. No custom integration project. No presenter standing by."
          primaryCta="Start free trial"
          primaryHref={`${dashboardUrl}/signup`}
          composition="steps"
          compositionImages={[media.heroHow]}
          imageAlt="Drop a PPTX or PDF and watch indexing progress"
        />

        <StepsTimeline
          eyebrow="Step by step"
          title="The Overtone presentation loop"
          steps={[
            { title: "Upload your deck", body: "Dashboard ingests PPTX/PDF. Vision extracts per-slide content. pgvector stores searchable chunks.", image: media.stepUpload },
            { title: "Wait for indexing", body: "Status moves from uploaded → indexing → ready. Large decks process in the background.", image: media.fragIngest },
            { title: "Launch the bot", body: "Paste meeting URL, pick the deck, click Launch. Recall joins and opens presenter as camera.", image: media.stepLaunch },
            { title: "Present & answer", body: "Voice agent speaks, navigates slides, and answers from indexed content — live in the meeting.", image: media.stepPresent },
          ]}
        />
      </ToneBand>

      <ToneBand tone="light">
        <SplitFeature
          eyebrow="Behind the scenes"
          title="What happens under the hood"
          body="Upload flows through vision indexing into Postgres + pgvector. Launch creates a Recall bot with a signed presenter URL. Audio streams through a backend realtime relay to Gemini Live. Tool calls stay on the server — grounded in your deck."
          bullets={["FastAPI backend · React presenter · React dashboard", "Recall.ai for meeting join · GCS for deck storage", "Workspace-isolated multi-tenant SaaS"]}
          imageSrc={media.fragWorkspace}
          imageAlt="Workspace catalog rows"
          tone="light"
          reverse
        />

        <FeatureGrid
          eyebrow="Requirements"
          title="What you need to get started"
          subtitle="Three things. That's it."
          items={checklist}
        />
      </ToneBand>

      <CTABand
        title="Try the full loop — free"
        subtitle="Upload a deck, launch a bot, and see Overtone present live."
        primaryLabel="Start free trial"
        primaryHref={`${dashboardUrl}/signup`}
        secondaryLabel="Explore features"
        secondaryHref="/features"
      />
    </>
  );
}
