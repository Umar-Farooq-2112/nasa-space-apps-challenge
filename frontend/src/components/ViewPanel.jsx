import React from "react";

const MODES = [
  ["flip", "Flipbook"],
  ["composite", "Time-colour"],
  ["diff", "Difference"],
];

export default function ViewPanel({ sel, band, setBand, mode, setMode, sens, setSens }) {
  if (!sel) return null;
  const bands = Object.entries(sel.bands);
  return (
    <div className="card">
      <h2>4. View</h2>
      <div className="stack">
        <div>
          <label>Band (use one at a time)</label>
          <select value={band} onChange={(e) => setBand(e.target.value)} disabled={!bands.length}>
            {bands.length === 0 && <option value="">(no usable images)</option>}
            {bands.map(([b, n]) => <option key={b} value={b}>{b} ({n} images)</option>)}
          </select>
        </div>
        <div>
          <label>Picture</label>
          <div className="seg">
            {MODES.map(([id, text]) => (
              <button key={id} className={mode === id ? "on" : ""} onClick={() => setMode(id)}>{text}</button>
            ))}
          </div>
        </div>
        <div>
          <label>Mover sensitivity: {sens}&sigma; (lower finds fainter movers, but more false alarms)</label>
          <input type="range" min="3" max="8" step="0.5" value={sens} onChange={(e) => setSens(+e.target.value)} />
        </div>
      </div>
    </div>
  );
}
