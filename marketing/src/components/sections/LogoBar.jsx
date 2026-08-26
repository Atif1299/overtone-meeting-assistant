import { useScrollReveal } from "../../hooks/useScrollReveal.js";

export default function LogoBar({ title = "Works with the platforms your buyers already use" }) {
  const ref = useScrollReveal();
  const logos = ["Google Meet", "Zoom", "Microsoft Teams", "Recall.ai", "Gemini Live"];

  return (
    <section className="logo-bar section-dark reveal" ref={ref}>
      <p className="logo-bar-title">{title}</p>
      <div className="logo-bar-row">
        {logos.map((name) => (
          <span key={name} className="logo-pill">{name}</span>
        ))}
      </div>
    </section>
  );
}
