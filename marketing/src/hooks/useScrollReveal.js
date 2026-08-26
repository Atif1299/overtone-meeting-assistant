import { useEffect, useRef } from "react";

export function useScrollReveal(options = {}) {
  const ref = useRef(null);
  const {
    threshold = 0.15,
    rootMargin = "0px 0px -8% 0px",
    stagger = false,
  } = options;

  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      el.classList.add("in-view");
      el.querySelectorAll(".reveal-item").forEach((child) => child.classList.add("in-view"));
      return undefined;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("in-view");
          if (stagger) {
            entry.target.querySelectorAll(".reveal-item").forEach((child, i) => {
              child.style.setProperty("--reveal-i", i);
              child.classList.add("in-view");
            });
          }
          observer.unobserve(entry.target);
        });
      },
      { threshold, rootMargin }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [threshold, rootMargin, stagger]);

  return ref;
}
