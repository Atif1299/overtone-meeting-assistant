import {
  siGooglemeet,
  siZoom,
  siGooglegemini,
  siStripe,
} from "simple-icons";

const EXTERNAL = {
  microsoftteams: {
    title: "Microsoft Teams",
    src: "https://upload.wikimedia.org/wikipedia/commons/c/c9/Microsoft_Office_Teams_%282018%E2%80%93present%29.svg",
  },
  recall: {
    title: "Recall.ai",
    src: "https://www.recall.ai/favicon.svg",
  },
};

function fromSimple(icon) {
  return { type: "simple", title: icon.title, hex: icon.hex, path: icon.path };
}

function fromExternal(key) {
  const icon = EXTERNAL[key];
  return { type: "external", title: icon.title, src: icon.src };
}

export const integrations = [
  { id: "googlemeet", label: "Google Meet", ...fromSimple(siGooglemeet) },
  { id: "zoom", label: "Zoom", ...fromSimple(siZoom) },
  { id: "microsoftteams", label: "Microsoft Teams", ...fromExternal("microsoftteams") },
  { id: "recall", label: "Recall.ai", ...fromExternal("recall") },
  { id: "googlegemini", label: "Gemini Live", ...fromSimple(siGooglegemini) },
  { id: "stripe", label: "Stripe", ...fromSimple(siStripe) },
];
