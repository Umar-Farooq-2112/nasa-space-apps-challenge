import React, { useEffect, useRef, useState } from "react";
import Curve from "./Curve.jsx";

// What to say when there is nothing to show yet.
function emptyMessage(sel, onGuide) {
  if (!sel) return <>Create a dataset on the left to begin.</>;
  if (sel.n_files === 0) return <>Add FITS images on the left. Not sure where to get them? <button className="link" onClick={onGuide}>Open the guide</button>.</>;
  if (sel.n_ok === 0 && sel.n_needs_centre > 0) return <>These images are big. Enter the <b>RA and Dec</b> of your target in <b>Sky position</b> and press Apply, and I will crop around it.</>;
  if (sel.n_ok === 0 && sel.n_outside > 0) return <>None of the images cover RA {sel.effective_centre?.[0].toFixed(4)}, Dec {sel.effective_centre?.[1].toFixed(4)}. Change the position or press Clear.</>;
  if (sel.n_ok === 0) return <>None of the files could be used. Check the list on the left for the reasons.</>;
  return null;
}

export default function Viewer({ sel, view, mode, moverState, selectedMover, onSelectMover, onGuide }) {
  const { frames, imgs, still, busy } = view;
  const { movers, note, busy: moversBusy, nFrames } = moverState;
  const canvas = useRef();
  const [idx, setIdx] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(1);
  const [showArt, setShowArt] = useState(false);          // show suspected halos / ghosts too
  const nArt = movers.filter((m) => m.artifact).length;
  const nReal = movers.length - nArt;
  const visible = (m) => !m.artifact || showArt;
  const flip = mode === "flip";
  const cur = flip ? Math.min(idx, Math.max(frames.length - 1, 0)) : frames.length - 1;
  const ready = frames.length > 0 && (flip ? imgs.length === frames.length : !!still);

  useEffect(() => { setIdx(0); setPlaying(true); }, [frames, mode]);

  useEffect(() => {                                           // play loop
    if (!playing || !flip || frames.length < 2) return;
    const t = setInterval(() => setIdx((i) => (i + 1) % frames.length), 450 / speed);
    return () => clearInterval(t);
  }, [playing, flip, frames, speed]);

  useEffect(() => {                                           // keyboard: space, arrows
    const onKey = (e) => {
      if (["INPUT", "SELECT", "TEXTAREA"].includes(e.target.tagName) || !flip || !frames.length) return;
      if (e.code === "Space") { e.preventDefault(); setPlaying((p) => !p); }
      if (e.code === "ArrowRight") { setPlaying(false); setIdx((i) => (i + 1) % frames.length); }
      if (e.code === "ArrowLeft") { setPlaying(false); setIdx((i) => (i - 1 + frames.length) % frames.length); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [flip, frames]);

  const pos = (p) => {
    const c = canvas.current, s = frames[cur].scale;
    return [(p.px + 0.5) * s, c.height - (p.py + 0.5) * s];
  };

  useEffect(() => {                                           // draw picture + circles + trails
    const c = canvas.current;
    if (!c || !ready) return;
    const im = flip ? imgs[cur] : still;
    c.width = im.naturalWidth; c.height = im.naturalHeight;
    const g = c.getContext("2d");
    g.drawImage(im, 0, 0);
    movers.forEach((m, k) => {
      if (!visible(m)) return;
      const col = k === selectedMover ? "#ffd23f" : m.artifact ? "#ff9f43" : "#4de1ff";
      g.strokeStyle = col; g.lineWidth = 2; g.beginPath();
      m.points.slice(0, cur + 1).forEach((p, i) => { const [x, y] = pos(p); i ? g.lineTo(x, y) : g.moveTo(x, y); });
      g.stroke();
      const [x, y] = pos(m.points[cur]);
      g.beginPath(); g.arc(x, y, 14, 0, 7); g.stroke();
      g.fillStyle = col; g.font = "bold 14px sans-serif";
      g.fillText(`#${k + 1}  ${m.rate_arcsec_per_year.toFixed(1)}"/yr`, x + 18, y - 6);
    });
  }, [ready, imgs, still, cur, movers, selectedMover, flip, showArt]); // eslint-disable-line react-hooks/exhaustive-deps

  const onClick = (e) => {                                    // click a circle to select it
    if (!nReal && !(showArt && nArt)) return;
    const c = canvas.current, r = c.getBoundingClientRect(), k = c.width / r.width;
    const cx = (e.clientX - r.left) * k, cy = (e.clientY - r.top) * k;
    let best = -1, bd = 30;
    movers.forEach((m, i) => { if (!visible(m)) return; const [x, y] = pos(m.points[cur]); const d = Math.hypot(x - cx, y - cy); if (d < bd) { bd = d; best = i; } });
    onSelectMover(best === selectedMover ? -1 : best);
  };

  const empty = emptyMessage(sel, onGuide);
  const f = frames[cur];
  const caption = !ready ? "" : flip
    ? `Frame ${cur + 1} of ${frames.length}  |  ${f.date.replace("T", " ")} UTC  |  ${f.band}`
    : `${mode === "composite" ? "Time-colour picture" : "Difference picture"} of ${frames.length} images, ${frames[0].date.slice(0, 10)} to ${frames[frames.length - 1].date.slice(0, 10)}`;

  return (
    <div>
      {sel && sel.n_ok > 0 && sel.n_needs_centre + sel.n_outside > 0 && (
        <div className="notice warn">
          {sel.n_needs_centre + sel.n_outside} file(s) are not shown: {sel.n_needs_centre > 0 && "big images need an RA/Dec"}
          {sel.n_needs_centre > 0 && sel.n_outside > 0 && ", "}{sel.n_outside > 0 && "some do not cover the position"}. See the list on the left.
        </div>
      )}
      <div className="stage">
        {empty && <div className="empty">{empty}</div>}
        {!empty && !ready && <div className="empty">{busy ? "Loading pictures..." : mode !== "flip" && frames.length < 2 ? "Need at least 2 usable images for this picture." : ""}</div>}
        <canvas ref={canvas} onClick={onClick} style={{ display: ready && !empty ? "block" : "none", cursor: movers.length ? "pointer" : "default" }} />
        {busy && ready && <div className="busy">updating...</div>}
      </div>
      <div className="small muted" style={{ marginTop: 6 }}>{caption}</div>

      {ready && flip && (
        <div className="controls">
          <button onClick={() => setPlaying((p) => !p)} style={{ minWidth: 70 }}>{playing ? "Pause" : "Play"}</button>
          <input type="range" min="0" max={frames.length - 1} value={cur}
            onChange={(e) => { setPlaying(false); setIdx(+e.target.value); }} />
          <select value={speed} onChange={(e) => setSpeed(+e.target.value)} title="Playback speed">
            <option value={0.5}>0.5x</option><option value={1}>1x</option><option value={2}>2x</option><option value={4}>4x</option>
          </select>
          <span className="small muted">Space = play/pause, arrows = step</span>
        </div>
      )}

      {sel && sel.n_ok > 0 && (
        <div style={{ marginTop: 8 }}>
          {moversBusy && <div className="muted small">Looking for movers...</div>}
          {!moversBusy && note && <div className="notice info">{note}</div>}
          {!moversBusy && !note && ready && nReal === 0 && (
            <div className="notice">Mover Spotter found nothing moving. Try a lower sensitivity.</div>
          )}
          {movers.length > 0 && (
            <>
              {nReal > 0 && <div><b>{nReal} mover{nReal > 1 ? "s" : ""} found.</b> <span className="muted small">Click a circle in the picture, or a card below, to see its brightness over time.</span></div>}
              {nArt > 0 && (
                <label className="small" style={{ display: "block", margin: "6px 0", color: "var(--text)" }}>
                  <input type="checkbox" checked={showArt} onChange={(e) => { setShowArt(e.target.checked); onSelectMover(-1); }} style={{ width: "auto", marginRight: 6 }} />
                  Show {nArt} suspected ghost{nArt > 1 ? "s" : ""}/halo{nArt > 1 ? "s" : ""} (fake sources that travel with a very bright star)
                </label>
              )}
              <div className="moverlist">
                {movers.map((m, k) => visible(m) && (
                  <button key={k} className={"mover" + (k === selectedMover ? " sel" : "")} onClick={() => onSelectMover(k === selectedMover ? -1 : k)}
                    style={m.artifact ? { borderStyle: "dashed" } : undefined}>
                    <b style={m.artifact ? { color: "#ff9f43" } : undefined}>#{k + 1}</b> &nbsp;{m.rate_arcsec_per_year.toFixed(1)} arcsec/yr<br />
                    <span className="small muted">
                      seen in {m.n_detections} of {nFrames} images
                      {m.artifact === "halo" && <> &middot; glare around #{m.of + 1}</>}
                      {m.artifact === "comoving" && <> &middot; moves with #{m.of + 1}: optical ghost or companion</>}
                    </span>
                  </button>
                ))}
              </div>
              {selectedMover >= 0 && movers[selectedMover] && (
                <Curve mover={movers[selectedMover]} dates={frames.map((fr) => fr.date)}
                  label={`Mover #${selectedMover + 1}: brightness over time (3x3 pixel sum, image units)`} />
              )}
            </>
          )}
        </div>
      )}

      <details>
        <summary style={{ cursor: "pointer" }}><b>How to read this</b></summary>
        <ul>
          <li><b>Flipbook:</b> each frame is a different date. Stars stay in place; something that <i>drifts</i> is moving across the sky.</li>
          <li><b>Circle + trail:</b> Mover Spotter found a source whose position changes steadily. The label is its speed in arcseconds per year. It must appear in most frames, so one-off specks are ignored.</li>
          <li><b>Time-colour:</b> every date gets a colour and all frames are stacked. Fixed stars come out white. A mover leaves a rainbow trail, blue where it was long ago and red where it is newest.</li>
          <li><b>Difference:</b> newest third minus oldest third. Fixed stars cancel. A mover is a <span style={{ color: "#6c8cff" }}>blue</span> spot where it was and a <span style={{ color: "#ff6c6c" }}>red</span> spot where it is now.</li>
          <li><b>Band:</b> use one band at a time. Different bands show different stars, so mixing them looks like movement.</li>
        </ul>
      </details>
    </div>
  );
}
