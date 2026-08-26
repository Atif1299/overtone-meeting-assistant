import { Upload, Rocket, Radio, Sparkles, CreditCard, Building2, Briefcase, TrendingUp, UsersRound, FileText, Link2, UserPlus } from "lucide-react";
import { useScrollReveal } from "../../hooks/useScrollReveal.js";

const ICONS = {
  upload: Upload,
  rocket: Rocket,
  radio: Radio,
  sparkles: Sparkles,
  billing: CreditCard,
  workspace: Building2,
  briefcase: Briefcase,
  trending: TrendingUp,
  users: UsersRound,
  deck: FileText,
  link: Link2,
  account: UserPlus,
};

export default function FeatureGrid({ eyebrow, title, subtitle, items, columns = 3 }) {
  const ref = useScrollReveal();

  return (
    <section className="section section-light section-elevated scroll-fade" ref={ref}>
      <div className="section-mesh section-mesh--light" aria-hidden="true" />
      <div className="section-inner">
        <div className="section-head centered">
          {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
          <h2>{title}</h2>
          {subtitle ? <p className="muted section-sub">{subtitle}</p> : null}
        </div>
        <div className={`feature-grid feature-grid--${columns}`}>
          {items.map((item) => {
            const Icon = item.iconKey ? ICONS[item.iconKey] : null;
            return (
              <article key={item.title} className="feature-card card-hover">
                {item.image ? (
                  <div className="feature-card__media">
                    <img src={item.image} alt="" loading="lazy" />
                  </div>
                ) : null}
                <div className="feature-card__body">
                  {Icon ? (
                    <span className="feature-card__icon" aria-hidden="true">
                      <Icon size={18} strokeWidth={2} />
                    </span>
                  ) : null}
                  <h3>{item.title}</h3>
                  <p>{item.body}</p>
                </div>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
