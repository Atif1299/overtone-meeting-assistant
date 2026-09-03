import { useInView } from "../../hooks/useInView.js";

export default function RevealSection({ as: Tag = "section", className = "", children, ...rest }) {
  const [ref, visible] = useInView({ threshold: 0.08, rootMargin: "0px 0px -4% 0px" });

  return (
    <Tag ref={ref} className={`${className}${visible ? " is-visible" : ""}`.trim()} {...rest}>
      {children}
    </Tag>
  );
}
