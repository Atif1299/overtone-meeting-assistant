import { useScrollReveal } from "../../hooks/useScrollReveal.js";

export default function ComparisonTable({ rows, plans = ["Free", "Starter", "Pro"] }) {
  const ref = useScrollReveal();

  return (
    <section className="section section-dark reveal" ref={ref}>
      <div className="section-head centered">
        <p className="eyebrow">Compare plans</p>
        <h2>Everything included, side by side</h2>
      </div>
      <div className="compare-wrap">
        <table className="compare-table">
          <thead>
            <tr>
              <th>Feature</th>
              {plans.map((p) => (
                <th key={p}>{p}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.feature}>
                <td>{row.feature}</td>
                {row.values.map((v, i) => (
                  <td key={plans[i]}>{v}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
