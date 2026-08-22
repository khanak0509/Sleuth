import "./EvidenceCard.css";

const PINS = [
  "var(--pin-red)",
  "var(--pin-orange)",
  "var(--pin-green)",
  "var(--pin-purple)",
  "var(--pin-teal)",
  "var(--pin-yellow)",
];

export default function EvidenceCard({ doc, index, variant = "local", style, cardRef }) {
  const pin = variant === "web" ? "var(--pin-blue)" : PINS[index % PINS.length];
  const rot = style?.["--rot"] || `${(index % 2 === 0 ? -1 : 1) * (1.2 + (index % 3))}deg`;

  return (
    <article
      ref={cardRef}
      className={`evidence-card ${variant}`}
      style={{ ...style, "--rot": rot, "--pin": pin }}
    >
      <span className="pushpin" aria-hidden="true" />
      <header className="evidence-meta">
        <span className="repo">{doc.repo || "unknown"}</span>
        <span className="etype">{doc.event_type || (variant === "web" ? "WEB" : "LOG")}</span>
      </header>
      <p className="evidence-body">{doc.text || doc.body || ""}</p>
      {doc.timestamp ? <footer className="evidence-ts">{doc.timestamp}</footer> : null}
      {doc.score != null ? <span className="score">{Number(doc.score).toFixed(2)}</span> : null}
    </article>
  );
}
