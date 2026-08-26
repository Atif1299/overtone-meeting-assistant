import { useScrollReveal } from "../../hooks/useScrollReveal.js";
import { platforms } from "../visuals/platforms.js";
import PlatformLogo from "../visuals/PlatformLogo.jsx";

export default function LogoBar({ title = "Works with the platforms your buyers already use" }) {
  const ref = useScrollReveal();

  return (
    <section className="logo-bar section-dark scroll-reveal" ref={ref}>
      <p className="logo-bar-title">{title}</p>
      <div className="logo-bar-grid">
        {platforms.map((p) => (
          <PlatformLogo key={p.id} platform={p} size="md" showLabel />
        ))}
      </div>
    </section>
  );
}
