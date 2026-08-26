import { Briefcase, TrendingUp, UsersRound } from "lucide-react";
import { dashboardUrl } from "../config.js";
import { media } from "../components/visuals/media.js";
import HeroSection from "../components/sections/HeroSection.jsx";
import FeatureGrid from "../components/sections/FeatureGrid.jsx";
import SplitFeature from "../components/sections/SplitFeature.jsx";
import MetricsBand from "../components/sections/MetricsBand.jsx";
import CTABand from "../components/sections/CTABand.jsx";

const personas = [
  { iconKey: "briefcase", title: "Sales & solutions", body: "Run repeatable product demos without pulling senior engineers into every call. Stay on-deck when prospects go off-script.", image: media.botMeeting },
  { iconKey: "trending", title: "Founders & fundraising", body: "Pitch investors with a consistent narrative. Answer diligence questions from the actual slide — not from memory.", image: media.slideNavigation },
  { iconKey: "users", title: "Customer success", body: "Onboard accounts with the same playbook deck. Scale walkthroughs without scheduling conflicts.", image: media.heroDashboard },
];

export default function UseCasesPage() {
  return (
    <>
      <HeroSection
        badge="Use cases"
        title="Where Overtone wins — live meetings that need your deck, not a chatbot"
        subtitle="Sales demos, investor updates, customer onboarding, and any scenario where slides and voice matter."
        primaryCta="Start free trial"
        primaryHref={`${dashboardUrl}/signup`}
        imageSrc={media.botMeeting}
      />

      <FeatureGrid
        eyebrow="Personas"
        title="Built for teams who live in the meeting"
        subtitle="Same platform — different outcomes depending on who launches the bot."
        items={personas}
      />

      <SplitFeature
        eyebrow="Scenario"
        title="The investor asks about slide 9 — Overtone navigates and answers"
        body="In a live fundraise call, an investor jumps to unit economics on a slide you didn't plan to cover. Overtone receives the question, navigates to the right slide, searches indexed content, and responds in natural voice — grounded in what you uploaded."
        bullets={["No 'let me get back to you on that'", "Slide navigation on audience demand", "Consistent messaging across every call"]}
        imageSrc={media.voiceLive}
        tone="dark"
      />

      <MetricsBand
        metrics={[
          { value: "3×", label: "More demos per rep per week" },
          { value: "0", label: "Engineers required per call" },
          { value: "100%", label: "On-deck answer rate" },
          { value: "<5 min", label: "Time to first launch" },
        ]}
      />

      <CTABand
        title="Pick your use case — start free"
        subtitle="Upload your deck and launch your first bot today."
        primaryLabel="Start free trial"
        primaryHref={`${dashboardUrl}/signup`}
        secondaryLabel="See pricing"
        secondaryHref="/pricing"
      />
    </>
  );
}
