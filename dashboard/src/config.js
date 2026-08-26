export const marketingUrl = import.meta.env.VITE_MARKETING_URL || "http://127.0.0.1:5177";

export const marketingNav = [
  { href: `${marketingUrl}/features`, label: "Features" },
  { href: `${marketingUrl}/pricing`, label: "Pricing" },
  { href: `${marketingUrl}/how-it-works`, label: "How it works" },
  { href: `${marketingUrl}/use-cases`, label: "Use cases" },
];
