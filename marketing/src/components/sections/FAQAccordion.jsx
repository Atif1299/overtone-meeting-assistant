import { useState } from "react";
import { useScrollReveal } from "../../hooks/useScrollReveal.js";

export default function FAQAccordion({ title, items }) {
  const ref = useScrollReveal();
  const [open, setOpen] = useState(0);

  return (
    <section className="section section-light reveal" ref={ref}>
      <div className="section-head centered">
        <p className="eyebrow">FAQ</p>
        <h2>{title}</h2>
      </div>
      <div className="faq-list">
        {items.map((item, i) => (
          <div key={item.q} className={`faq-item${open === i ? " open" : ""}`}>
            <button type="button" className="faq-q" onClick={() => setOpen(open === i ? -1 : i)}>
              {item.q}
              <span aria-hidden="true">{open === i ? "−" : "+"}</span>
            </button>
            {open === i ? <p className="faq-a">{item.a}</p> : null}
          </div>
        ))}
      </div>
    </section>
  );
}
