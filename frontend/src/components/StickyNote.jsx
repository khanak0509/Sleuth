import "./StickyNote.css";

export default function StickyNote({ children, className = "", style, pulsing }) {
  return (
    <aside
      className={`sticky-note ${className} ${pulsing ? "pulse" : ""}`}
      style={style}
    >
      <span className="sticky-pin" aria-hidden="true" />
      {children}
    </aside>
  );
}
