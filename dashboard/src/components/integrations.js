import {
  siGooglemeet,
  siZoom,
  siGooglegemini,
  siStripe,
} from "simple-icons";

const LOCAL = {
  microsoftteams: {
    title: "Microsoft Teams",
    src: "/media/logos/logo-microsoft-teams.png",
    variant: "icon",
  },
  recall: {
    title: "Recall.ai",
    src: "/media/logos/logo-recall-ai.png",
    iconSrc: "/media/logos/logo-recall-icon.png",
    variant: "wordmark",
  },
};

function fromSimple(icon) {
  return { type: "simple", title: icon.title, hex: icon.hex, path: icon.path };
}

function fromLocal(key) {
  const icon = LOCAL[key];
  return {
    type: "local",
    title: icon.title,
    src: icon.src,
    iconSrc: icon.iconSrc,
    variant: icon.variant || "icon",
  };
}

export const integrations = [
  { id: "googlemeet", label: "Google Meet", ...fromSimple(siGooglemeet) },
  { id: "zoom", label: "Zoom", ...fromSimple(siZoom) },
  { id: "microsoftteams", label: "Microsoft Teams", ...fromLocal("microsoftteams") },
  { id: "recall", label: "Recall.ai", ...fromLocal("recall") },
  { id: "googlegemini", label: "Gemini Live", ...fromSimple(siGooglegemini) },
  { id: "stripe", label: "Stripe", ...fromSimple(siStripe) },
];
