import { useScrollReveal } from "../../hooks/useScrollReveal.js";

export default function ScrollReveal({ children, className = "", stagger = false, as: Tag = "div" }) {
  const ref = useScrollReveal({ stagger });

  return (
    <Tag ref={ref} className={`scroll-reveal${stagger ? " scroll-reveal--stagger" : ""} ${className}`.trim()}>
      {children}
    </Tag>
  );
}
