import "./Stamp.css";

export default function Stamp({ kind }) {
  if (!kind) return null;
  const label = kind === "closed" ? "CASE CLOSED" : "ESCALATING";
  return (
    <div className={`stamp stamp-${kind}`} aria-label={label}>
      {label}
    </div>
  );
}
