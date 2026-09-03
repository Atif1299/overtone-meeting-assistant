import { Star } from "lucide-react";
import { useScrollReveal } from "../../hooks/useScrollReveal.js";

function TestimonialCard({ item, duplicate = false }) {
  return (
    <blockquote className={`testimonial card-glass${duplicate ? " testimonial-dup" : ""}`}>
      <div className="testimonial-stars" aria-hidden="true">
        {Array.from({ length: 5 }, (_, i) => (
          <Star key={i} size={14} fill="currentColor" strokeWidth={0} />
        ))}
      </div>
      <p className="quote">"{item.quote}"</p>
      <footer>
        {item.avatar ? (
          <img src={item.avatar} alt="" className="testimonial-avatar" width={40} height={40} />
        ) : null}
        <span className="testimonial-who">
          <strong>{item.name}</strong>
          <span>{item.role}</span>
          <span className="testimonial-verified">Verified operator</span>
        </span>
      </footer>
    </blockquote>
  );
}

export default function TestimonialRow({ title, items, marquee = false }) {
  const ref = useScrollReveal();

  return (
    <section className="section section-testimonials scroll-fade" ref={ref}>
      <div className="section-mesh section-mesh--testimonials" aria-hidden="true" />
      <div className="section-inner">
        <div className="section-head centered">
          <p className="eyebrow">Social proof</p>
          <h2>{title}</h2>
        </div>
        {marquee ? (
          <div className="testimonial-marquee">
            <div className="testimonial-marquee-track">
              {items.map((item) => (
                <TestimonialCard key={item.name} item={item} />
              ))}
              {items.map((item) => (
                <TestimonialCard key={`${item.name}-dup`} item={item} duplicate />
              ))}
            </div>
          </div>
        ) : (
          <div className="testimonial-grid">
            {items.map((item) => (
              <TestimonialCard key={item.name} item={item} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
