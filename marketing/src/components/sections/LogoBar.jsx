import { useScrollReveal } from "../../hooks/useScrollReveal.js";
import BrandLogo from "../visuals/BrandLogo.jsx";
import { integrations } from "../visuals/integrations.js";

export default function LogoBar({ title = "Works with the platforms your buyers already use" }) {
  const ref = useScrollReveal({ variant: "fade" });

  return (
    <section className="logo-bar section-dark scroll-fade" ref={ref}>
      <p className="logo-bar-title">{title}</p>
      <div className="logo-bar-row">
        {integrations.map((item) => (
          <div key={item.id} className="logo-pill logo-pill--brand">
            <BrandLogo brand={item} size={22} />
            <span>{item.label}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
