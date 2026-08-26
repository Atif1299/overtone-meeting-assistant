import { useScrollReveal } from "../../hooks/useScrollReveal.js";

export default function TestimonialRow({ title, items }) {
  const ref = useScrollReveal();

  return (
    <section className="section section-testimonials scroll-fade" ref={ref}>
      <div className="section-mesh section-mesh--testimonials" aria-hidden="true" />
      <div className="section-inner">
        <div className="section-head centered">
          <p className="eyebrow">Social proof</p>
          <h2>{title}</h2>
        </div>
        <div className="testimonial-grid">
          {items.map((t) => (
            <blockquote key={t.quote} className="testimonial card-glass card-hover">
              <div className="testimonial-stars" aria-hidden="true">★★★★★</div>
              <p className="quote">"{t.quote}"</p>
              <footer>
                <strong>{t.name}</strong>
                <span>{t.role}</span>
              </footer>
            </blockquote>
          ))}
        </div>
      </div>
    </section>
  );
}
