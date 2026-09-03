import {
  siGooglemeet,
  siZoom,
  siGooglegemini,
  siStripe,
} from "simple-icons";

/** Microsoft Teams is no longer exported by simple-icons; same SVG path + hex as the last official mark. */
const siMicrosoftteams = {
  title: "Microsoft Teams",
  hex: "6264A7",
  path: "M20.625 8.438v7.5a2.812 2.812 0 0 1-2.813 2.812h-3.75v-6.563a3.75 3.75 0 0 0-3.75-3.75H8.438V6.563A2.812 2.812 0 0 1 11.25 3.75h6.562a2.812 2.812 0 0 1 2.813 2.688zm-9.375 3.124a2.813 2.813 0 1 1-5.625 0 2.813 2.813 0 0 1 5.625 0zM3.75 20.625a3.75 3.75 0 0 1 3.75-3.75h3.75a3.75 3.75 0 0 1 3.75 3.75v.938H3.75z",
};

const siRecall = {
  title: "Recall.ai",
  hex: "007BFF",
  path: "M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16z",
};

function fromSimple(icon) {
  return {
    type: "simple",
    title: icon.title,
    hex: icon.hex,
    path: icon.path,
  };
}

export const integrations = [
  { id: "googlemeet", label: "Google Meet", ...fromSimple(siGooglemeet) },
  { id: "zoom", label: "Zoom", ...fromSimple(siZoom) },
  { id: "microsoftteams", label: "Microsoft Teams", ...fromSimple(siMicrosoftteams) },
  { id: "recall", label: "Recall.ai", ...fromSimple(siRecall) },
  { id: "googlegemini", label: "Gemini Live", ...fromSimple(siGooglegemini) },
  { id: "stripe", label: "Stripe", ...fromSimple(siStripe) },
];
