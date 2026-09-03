import { dashboardUrl } from "../config.js";
import { media } from "../components/visuals/media.js";
import HeroSection from "../components/sections/HeroSection.jsx";
import LogoBar from "../components/sections/LogoBar.jsx";
import SplitFeature from "../components/sections/SplitFeature.jsx";
import StepsTimeline from "../components/sections/StepsTimeline.jsx";
import TestimonialRow from "../components/sections/TestimonialRow.jsx";
import MetricsBand from "../components/sections/MetricsBand.jsx";
import FAQAccordion from "../components/sections/FAQAccordion.jsx";
import CTABand from "../components/sections/CTABand.jsx";
import ToneBand from "../components/sections/ToneBand.jsx";

const homeFaq = [
  { q: "Does Overtone replace a human presenter entirely?", a: "Overtone handles scripted presentation flow and grounded Q&A from your deck. Many teams use it for first-pass demos, onboarding, and investor updates — with humans joining for negotiation or custom deep dives." },
  { q: "Which meeting platforms are supported?", a: "Google Meet, Zoom, and Microsoft Teams via Recall.ai bots. Paste the meeting URL in Launch and Overtone joins as the presenter camera." },
  { q: "How are answers kept on-deck?", a: "Every slide is indexed into pgvector. The voice agent uses search_and_answer and slide tools — responses come from uploaded content, not open-web knowledge." },
  { q: "What's included in the free trial?", a: "1 deck upload and 1 bot launch per month. Full presenter experience, agent studio, and community support. No credit card on signup." },
];

export default function HomePage() {
  return (
    <>
      <ToneBand tone="dark" glow>
        <HeroSection
          badge="AI presentation agent for live meetings"
          title="Your deck. Your meeting. Overtone presents and answers live."
          subtitle="Upload slides, paste a Meet / Zoom / Teams link, and let Overtone join as a presenter — navigating your deck and answering questions grounded in your content."
          primaryCta="Start free trial"
          primaryHref={`${dashboardUrl}/signup`}
          secondaryCta="See how it works"
          secondaryHref="/how-it-works"
          overlay
          overlayImages={[media.heroHome, media.fragLaunch, media.fragSession]}
          imageAlt="Overtone product fragments — overview, launch, and live session"
        />

        <LogoBar />
      </ToneBand>

      <SplitFeature
        eyebrow="The problem"
        title="Manual demos don't scale — and generic AI can't stay on your slides"
        body="Sales teams, founders, and customer success leaders repeat the same presentation dozens of times. Hiring more humans doesn't scale. Generic chatbots hallucinate when investors ask about slide 7."
        bullets={[
          "Every answer should come from your deck — not the open web",
          "Live meetings need voice, slide control, and interruption handling",
          "You need one operator studio — not five disconnected tools",
        ]}
        tone="light"
      />

      <ToneBand tone="dark">
        <SplitFeature
          eyebrow="Product spotlight"
          title="A presenter that joins the call, shows your slides, and speaks with context"
          body="Overtone indexes your PPTX or PDF, launches a Recall.ai bot into the meeting, and drives a realtime voice agent that navigates slides and answers from indexed content."
          bullets={[
            "Deck-grounded Q&A via search_and_answer tools",
            "Gemini Live speech-to-speech with natural pacing",
            "Slide navigation on audience demand",
          ]}
          imageSrc={media.fragAgent}
          imageAlt="Agent studio instructions"
          tone="dark"
          reverse
        />

        <StepsTimeline
        eyebrow="How it works"
        title="Four steps from upload to live presentation"
        ctaLabel="Full walkthrough →"
        ctaTo="/how-it-works"
        steps={[
          { title: "Upload", body: "Ingest PPTX/PDF. Vision extracts per-slide metadata into pgvector.", image: media.stepUpload },
          { title: "Launch", body: "Paste a meeting URL. Recall opens the presenter as bot camera.", image: media.stepLaunch },
          { title: "Present", body: "Gemini Live speaks through the meeting with slide control tools.", image: media.stepPresent },
          { title: "Answer", body: "Audience questions trigger grounded search — not generic chat.", image: media.stepAnswer },
        ]}
      />
      </ToneBand>

      <TestimonialRow
        title="Built for teams who can't afford to wing live demos"
        marquee
        items={[
          { quote: "We stopped scheduling three engineers for every sales call. Overtone runs the deck and stays on-message.", name: "Alex R.", role: "Head of Sales, B2B SaaS", avatar: media.avatar1 },
          { quote: "Investors asked about unit economics on slide 9 — it navigated there and answered from our actual deck.", name: "Priya M.", role: "Founder, Seed-stage startup", avatar: media.avatar2 },
          { quote: "Customer onboarding used to mean the same 45-minute walkthrough. Now we launch a bot with the playbook deck.", name: "Jordan K.", role: "CS Lead, Series A", avatar: media.avatar3 },
          { quote: "Playbook walkthroughs no longer wait on my calendar. Every new account gets the same live onboarding from the deck.", name: "Casey N.", role: "Head of Customer Success, Series B", avatar: media.avatar6 },
        ]}
      />

      <MetricsBand
        metrics={[
          { value: "10s", label: "Average slide index time per page" },
          { value: "3", label: "Meeting platforms supported" },
          { value: "100%", label: "Answers grounded in your deck" },
          { value: "24/7", label: "Launch whenever the meeting starts" },
        ]}
      />

      <FAQAccordion title="Common questions" items={homeFaq} />

      <CTABand
        title="Ready to present without a human in the loop?"
        subtitle="Start free — 1 deck upload and 1 bot launch included. Upgrade when your demo volume grows."
        primaryLabel="Start free trial"
        primaryHref={`${dashboardUrl}/signup`}
        secondaryLabel="See pricing"
        secondaryHref="/pricing"
      />
    </>
  );
}
