import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import EvidenceCard from "./EvidenceCard";
import Stamp from "./Stamp";
import StickyNote from "./StickyNote";
import StringCanvas from "./StringCanvas";
import "./Corkboard.css";

const API = import.meta.env.VITE_API_URL || "";

function layoutDocs(n, boardW, boardH) {
  const cx = boardW / 2;
  const cy = Math.min(280, boardH * 0.32);
  const r = Math.min(boardW * 0.34, 280);
  const spots = [];
  for (let i = 0; i < n; i++) {
    const a = -Math.PI * 0.85 + (Math.PI * 1.7 * i) / Math.max(n - 1, 1);
    const x = cx + Math.cos(a) * r - 105;
    const y = cy + Math.sin(a) * (r * 0.55) + 40;
    const rot = `${((i % 5) - 2) * 1.1}deg`;
    spots.push({ left: x, top: Math.max(40, y), "--rot": rot });
  }
  return spots;
}

export default function Corkboard() {
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [res, setRes] = useState(null);
  const [status, setStatus] = useState({ event_count: 0, last_ingested_timestamp: null });
  const [pulse, setPulse] = useState(false);
  const [lines, setLines] = useState([]);
  const [showStamp, setShowStamp] = useState(false);
  const [showTool, setShowTool] = useState(false);
  const [err, setErr] = useState("");

  const boardRef = useRef(null);
  const queryRef = useRef(null);
  const docRefs = useRef([]);

  useEffect(() => {
    let prev = 0;
    const tick = async () => {
      try {
        const r = await fetch(`${API}/stream/status`);
        const j = await r.json();
        if (j.event_count !== prev) {
          setPulse(true);
          setTimeout(() => setPulse(false), 500);
          prev = j.event_count;
        }
        setStatus(j);
      } catch {
        /* ingest status optional while backend boots */
      }
    };
    tick();
    const id = setInterval(tick, 3000);
    return () => clearInterval(id);
  }, []);

  const measure = useCallback(() => {
    const board = boardRef.current;
    const qEl = queryRef.current;
    if (!board || !qEl || !res?.retrieved_docs?.length) {
      setLines([]);
      return;
    }
    const br = board.getBoundingClientRect();
    const qr = qEl.getBoundingClientRect();
    const qx = qr.left + qr.width / 2 - br.left;
    const qy = qr.top + qr.height / 2 - br.top;

    const next = [];
    docRefs.current.forEach((el) => {
      if (!el) return;
      const r = el.getBoundingClientRect();
      next.push({
        x1: qx,
        y1: qy,
        x2: r.left + r.width / 2 - br.left,
        y2: r.top + 8 - br.top,
      });
    });
    setLines(next);
  }, [res]);

  useLayoutEffect(() => {
    if (!res) return;
    const t = setTimeout(measure, 80);
    window.addEventListener("resize", measure);
    return () => {
      clearTimeout(t);
      window.removeEventListener("resize", measure);
    };
  }, [res, measure]);

  async function onSubmit(e) {
    e.preventDefault();
    if (!q.trim() || loading) return;
    setLoading(true);
    setErr("");
    setRes(null);
    setShowStamp(false);
    setShowTool(false);
    setLines([]);
    docRefs.current = [];

    try {
      const r = await fetch(`${API}/incident`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q.trim() }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      setRes(j);
      setTimeout(() => setShowStamp(true), 700);
      if (j.tool_used && j.tool_used !== "none") {
        setTimeout(() => setShowTool(true), 1000);
      }
    } catch (ex) {
      setErr(String(ex.message || ex));
    } finally {
      setLoading(false);
    }
  }

  const docs = res?.retrieved_docs || [];
  const boardW = boardRef.current?.clientWidth || 900;
  const boardH = boardRef.current?.clientHeight || 700;
  const spots = layoutDocs(docs.length, boardW, boardH);

  const stampKind =
    res && !res.rejected
      ? res.path_taken === "fallback"
        ? "escalating"
        : res.path_taken === "direct"
          ? "closed"
          : null
      : null;

  const webCard =
    res?.path_taken === "fallback"
      ? {
          repo: "web search",
          event_type: "FALLBACK",
          text: res.grade_reason
            ? `Escalated: ${res.grade_reason}`
            : "Local logs weak — used DuckDuckGo context.",
        }
      : null;

  return (
    <div className="corkboard" ref={boardRef}>
      <header className="brand">
        <h1>SLEUTH</h1>
        <p className="tagline">live github event incident board</p>
      </header>

      <StickyNote className="status-note" style={{ "--rot": "4deg" }} pulsing={pulse}>
        <span className="label">Live ingest</span>
        <span className="count" key={status.event_count}>
          {status.event_count ?? 0}
        </span>
        <span className="ts">
          {status.last_ingested_timestamp
            ? status.last_ingested_timestamp.slice(0, 19)
            : "waiting…"}
        </span>
      </StickyNote>

      <StringCanvas lines={lines} />

      {docs.map((d, i) => (
        <EvidenceCard
          key={`${d.repo}-${i}-${d.timestamp || i}`}
          doc={d}
          index={i}
          style={{
            left: spots[i]?.left,
            top: spots[i]?.top,
            "--rot": spots[i]?.["--rot"],
            animationDelay: `${i * 0.1}s`,
          }}
          cardRef={(el) => {
            docRefs.current[i] = el;
          }}
        />
      ))}

      {webCard ? (
        <EvidenceCard
          doc={webCard}
          index={docs.length}
          variant="web"
          style={{
            left: boardW / 2 + 160,
            top: Math.min(boardH * 0.55, 420),
            "--rot": "2.5deg",
            animationDelay: `${docs.length * 0.1 + 0.2}s`,
          }}
          cardRef={(el) => {
            docRefs.current[docs.length] = el;
          }}
        />
      ) : null}

      <form className="query-card" ref={queryRef} onSubmit={onSubmit}>
        <span className="pushpin query-pin" aria-hidden="true" />
        <span className="case-label">New Case</span>
        <textarea
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="What incident are we chasing?"
          rows={3}
          disabled={loading}
        />
        <button type="submit" disabled={loading || !q.trim()}>
          {loading ? "Pinning…" : "Investigate"}
        </button>
        {showStamp && stampKind ? <Stamp kind={stampKind} /> : null}
        {showTool && res?.tool_used && res.tool_used !== "none" ? (
          <StickyNote className="tool-note" style={{ "--rot": "-6deg" }}>
            tool: {res.tool_used}
          </StickyNote>
        ) : null}
      </form>

      {err ? <p className="err">{err}</p> : null}

      {res?.rejected ? (
        <section className="verdict rejected">
          <h2>Rejected</h2>
          <p>{res.answer}</p>
        </section>
      ) : null}

      {res && !res.rejected ? (
        <section className="verdict">
          <h2>Verdict</h2>
          <p className="path">
            path: {res.path_taken}
            {res.tool_used && res.tool_used !== "none" ? ` · tool: ${res.tool_used}` : ""}
          </p>
          <p className="answer">{res.answer}</p>
          {res.grade_reason ? <p className="grade">grade: {res.grade_reason}</p> : null}
        </section>
      ) : null}
    </div>
  );
}
