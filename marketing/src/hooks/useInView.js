import { useEffect, useRef, useState } from "react";

export function useInView(options = {}) {
  const ref = useRef(null);
  const [visible, setVisible] = useState(false);
  const {
    threshold = 0.12,
    rootMargin = "0px 0px -5% 0px",
    once = true,
  } = options;

  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setVisible(true);
      return undefined;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setVisible(true);
            if (once) observer.unobserve(entry.target);
          }
        });
      },
      { threshold, rootMargin }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [threshold, rootMargin, once]);

  return [ref, visible];
}

/** @deprecated use useInView instead */
export function useScrollReveal(options = {}) {
  const [ref, visible] = useInView(options);
  useEffect(() => {
    const el = ref.current;
    if (el && visible) el.classList.add("revealed");
  }, [ref, visible]);
  return ref;
}
