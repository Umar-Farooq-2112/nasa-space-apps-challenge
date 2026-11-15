import React, { useEffect, useRef } from "react";

// Brightness of one mover over time (3x3 pixel sum at its position in every frame).
export default function Curve({ mover, label, dates }) {
  const ref = useRef();
  useEffect(() => {
    const c = ref.current, g = c.getContext("2d");
    g.clearRect(0, 0, c.width, c.height);
    const pts = mover.points.map((p, i) => ({ f: p.flux, i })).filter((p) => p.f !== null);
    if (pts.length < 2) return;
    const lo = Math.min(...pts.map((p) => p.f)), hi = Math.max(...pts.map((p) => p.f));
    const X = (i) => 40 + (i / (mover.points.length - 1)) * (c.width - 55);
    const Y = (v) => c.height - 28 - ((v - lo) / (hi - lo || 1)) * (c.height - 50);
    g.strokeStyle = "#2c3857"; g.fillStyle = "#9aa6c4"; g.font = "11px sans-serif";
    g.beginPath(); g.moveTo(40, 10); g.lineTo(40, c.height - 28); g.lineTo(c.width - 10, c.height - 28); g.stroke();
    g.fillText(hi.toPrecision(3), 2, 18); g.fillText(lo.toPrecision(3), 2, c.height - 30);
    if (dates) {
      g.fillText(dates[0].slice(0, 4), 40, c.height - 10);
      const last = dates[dates.length - 1].slice(0, 4);
      g.fillText(last, c.width - 10 - g.measureText(last).width, c.height - 10);
    }
    g.strokeStyle = "#ffd23f"; g.lineWidth = 1.5; g.beginPath();
    pts.forEach((p, k) => (k ? g.lineTo(X(p.i), Y(p.f)) : g.moveTo(X(p.i), Y(p.f))));
    g.stroke();
    g.fillStyle = "#ffd23f";
    pts.forEach((p) => { g.beginPath(); g.arc(X(p.i), Y(p.f), 2.5, 0, 7); g.fill(); });
  }, [mover, dates]);
  return (
    <div style={{ marginTop: 10 }}>
      <div className="small muted">{label}</div>
      <canvas ref={ref} width={560} height={170} style={{ width: "100%", maxWidth: 560, background: "#10162a", border: "1px solid var(--line)", borderRadius: 8 }} />
    </div>
  );
}
