export default function StringCanvas({ lines }) {
  return (
    <svg className="string-layer" aria-hidden="true">
      {lines.map((l, i) => {
        const mx = (l.x1 + l.x2) / 2;
        const my = (l.y1 + l.y2) / 2 + 18;
        const d = `M ${l.x1} ${l.y1} Q ${mx} ${my} ${l.x2} ${l.y2}`;
        return (
          <path
            key={i}
            d={d}
            fill="none"
            stroke="var(--red-string)"
            strokeWidth="2"
            strokeLinecap="round"
            className="string-path"
            style={{ animationDelay: `${0.35 + i * 0.12}s` }}
          />
        );
      })}
    </svg>
  );
}
