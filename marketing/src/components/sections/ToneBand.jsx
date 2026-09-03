export default function ToneBand({ tone = "dark", glow = false, children }) {
  return (
    <div className={`tone-band tone-band--${tone}${glow ? " tone-band--glow" : ""}`}>
      {glow ? (
        <>
          <div className="tone-band__glow tone-band__glow--a" aria-hidden="true" />
          <div className="tone-band__glow tone-band__glow--b" aria-hidden="true" />
        </>
      ) : null}
      {children}
    </div>
  );
}
