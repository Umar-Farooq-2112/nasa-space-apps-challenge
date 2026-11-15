import { useEffect, useRef, useState, type ReactNode } from "react";
import { Contrast, Image as ImageIcon, Layers, Maximize2, Minimize2, Pause, Play, SkipBack, SkipForward } from "lucide-react";
import type { Frame, Mode, Mover } from "../api";
import { fmtDate, PIX } from "../lib";
import { reduceMotion } from "../hooks";
import { Segmented } from "./Bits";

const W = 1080;   // canvas resolution; CSS scales it to the plate size
const SPEEDS = [{ v: "700", label: "Slow" }, { v: "350", label: "Normal" }, { v: "150", label: "Fast" }] as const;
const MODES: { v: Mode; label: ReactNode; title: string }[] = [
  { v: "sky", label: <><ImageIcon size={15} />Photos</>, title: "The photos as NASA took them" },
  { v: "diff", label: <><Contrast size={15} />Changes only</>, title: "Each photo minus the average of all of them (key D): still stars vanish" },
  { v: "deep", label: <><Layers size={15} />Deep view</>, title: "All photos added together: about 3.5 times less noise, so faint objects appear" },
];
export const MODE_HINT: Record<Mode, string> = {
  sky: "The real photos, one per date. Watch for a dot that shifts while the other stars stay put.",
  diff: "Each photo minus the average of all of them. Still stars disappear; anything that moved or changed brightness shows up as a light or dark spot.",
  deep: "All photos added together into one image with about 3.5 times less noise, so faint objects appear. A moving object shows as a short streak.",
};

interface Props {
  title: string; coords: string; frames: Frame[]; imgs: (HTMLImageElement | null)[]; idx: number; setIdx: (i: number) => void;
  playing: boolean; setPlaying: (p: boolean) => void; speed: string; setSpeed: (s: string) => void; mode: Mode; setMode: (m: Mode) => void;
  movers: Mover[]; scale: number; selected: number; onSelect: (k: number) => void; overlay: ReactNode | null; status: string;
  max: boolean; setMax: (m: boolean) => void;
}

export function Viewer(p: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const last = useRef<HTMLImageElement | null>(null);
  const [drawIn, setDrawIn] = useState(1);
  const n = p.frames.length;
  const frame = p.frames[p.idx];

  // the one orchestrated moment: circles draw themselves around newly found movers
  useEffect(() => {
    if (!p.movers.length || reduceMotion) { setDrawIn(1); return; }
    let raf = 0; const t0 = performance.now();
    const step = (now: number) => { const k = Math.min(1, (now - t0) / 700); setDrawIn(k); if (k < 1) raf = requestAnimationFrame(step); };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [p.movers]);

  useEffect(() => {
    const c = canvas.current; if (!c) return;
    const ctx = c.getContext("2d"); if (!ctx) return;
    const im = p.imgs[p.idx] ?? last.current;   // keep the previous picture while a new mode's image loads
    ctx.fillStyle = "#0B1424"; ctx.fillRect(0, 0, W, W);
    if (!im || !n) { last.current = null; return; }
    last.current = im;
    ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = "high";
    ctx.drawImage(im, 0, 0, W, W);
    const k = W / (im.naturalWidth / p.scale), u = W / 720;
    const at = (q: { px: number; py: number }) => [(q.px + 0.5) * k, W - (q.py + 0.5) * k] as const;
    p.movers.forEach((m, j) => {
      const sel = j === p.selected, col = sel ? "#FFD23F" : "#FF4F8B";
      ctx.strokeStyle = col; ctx.lineWidth = 2 * u; ctx.globalAlpha = .9;
      ctx.beginPath();
      m.points.slice(0, p.idx + 1).forEach((q, i) => { const [x, y] = at(q); if (i) ctx.lineTo(x, y); else ctx.moveTo(x, y); });
      ctx.stroke();
      const pt = m.points[p.idx]; if (!pt) return;
      const [x, y] = at(pt), r = 22 * u;
      ctx.globalAlpha = 1; ctx.lineWidth = (sel ? 3 : 2.25) * u;
      ctx.beginPath(); ctx.arc(x, y, r, -Math.PI / 2, -Math.PI / 2 + 2 * Math.PI * drawIn); ctx.stroke();
      ctx.fillStyle = col; ctx.beginPath(); ctx.arc(x + r * .9, y - r * .9, 10 * u, 0, 7); ctx.fill();
      ctx.fillStyle = "#13294B"; ctx.font = `600 ${13 * u}px Geist, sans-serif`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText(String(j + 1), x + r * .9, y - r * .9 + .5 * u);
    });
  }, [p.idx, p.imgs, p.movers, p.selected, p.scale, drawIn, n]);

  function onCanvasClick(e: React.MouseEvent<HTMLCanvasElement>) {
    const im = last.current; if (!im || !p.movers.length) return;
    const r = e.currentTarget.getBoundingClientRect(), s = W / r.width;
    const cx = (e.clientX - r.left) * s, cy = (e.clientY - r.top) * s, k = W / (im.naturalWidth / p.scale);
    let best = -1, bd = 46 * (W / 720);
    p.movers.forEach((m, j) => {
      const q = m.points[p.idx]; if (!q) return;
      const d = Math.hypot((q.px + .5) * k - cx, W - (q.py + .5) * k - cy);
      if (d < bd) { bd = d; best = j; }
    });
    if (best >= 0) p.onSelect(best);
  }

  const im0 = p.imgs.find(Boolean);
  const scalePct = im0 ? (60 / PIX / (im0.naturalWidth / p.scale)) * 100 : 0;
  const pct = n > 1 ? (p.idx / (n - 1)) * 100 : 0;
  const step = (d: number) => { p.setPlaying(false); p.setIdx((p.idx + d + n) % n); };

  return (
    <div className={p.max ? "player max" : "player"} role={p.max ? "dialog" : undefined} aria-modal={p.max || undefined} aria-label={p.max ? `${p.title}, full view` : undefined}>
      {p.max && (
        <div className="max-head">
          <div><h2>{p.title}</h2><span className="num">{p.coords}</span></div>
          <button className="btn btn-ghost-dark" type="button" onClick={() => p.setMax(false)}><Minimize2 size={16} />Exit full view <kbd>Esc</kbd></button>
        </div>
      )}
      <div className="plate-wrap">
        <div className="plate">
          <canvas ref={canvas} width={W} height={W} onClick={onCanvasClick} aria-label="SPHEREx photo of the selected sky area" />
          <svg className="compass" width="46" height="46" viewBox="0 0 46 46" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <path d="M30 34V12M30 34H8" /><path d="M27 15l3-3 3 3M11 31l-3 3 3 3" />
            <text x="26.5" y="9" fill="currentColor" stroke="none" fontSize="10" fontWeight="600">N</text>
            <text x="0" y="38" fill="currentColor" stroke="none" fontSize="10" fontWeight="600">E</text>
          </svg>
          {frame && !p.overlay && <div className="stamp num">{fmtDate(frame.date)}</div>}
          {scalePct > 0 && !p.overlay && <div className="scalebar num"><i style={{ width: `${scalePct}%` }} />1 arcmin</div>}
          {!p.overlay && n > 0 && (
            <button className="plate-btn" type="button" onClick={() => p.setMax(!p.max)} title={p.max ? "Exit full view (Esc)" : "Full view (F)"} aria-label={p.max ? "Exit full view" : "Open full view"}>
              {p.max ? <Minimize2 size={17} /> : <Maximize2 size={17} />}
            </button>
          )}
          {p.overlay && <div className="overlay">{p.overlay}</div>}
        </div>
      </div>

      <div className="controls">
        <div className="timeline">
          <input type="range" min={0} max={Math.max(n - 1, 0)} value={p.idx} disabled={!n} aria-label="Photo"
            style={{ ["--p" as string]: `${pct}%` }} onChange={e => { p.setPlaying(false); p.setIdx(+e.target.value); }} />
          <div className="dates num">
            <span>{n ? fmtDate(p.frames[0].date) : ""}</span>
            <span>{n ? `Photo ${p.idx + 1} of ${n}` : ""}</span>
            <span>{n ? fmtDate(p.frames[n - 1].date) : ""}</span>
          </div>
        </div>
        <div className="control-row">
          <div className="transport">
            <button className="btn btn-outline btn-icon" type="button" onClick={() => step(-1)} disabled={!n} aria-label="Previous photo" title="Previous photo (left arrow)"><SkipBack size={16} /></button>
            <button className="btn btn-primary btn-icon play" type="button" onClick={() => p.setPlaying(!p.playing)} disabled={n < 2}
              aria-label={p.playing ? "Pause" : "Play"} title="Play or pause (space)">{p.playing ? <Pause size={18} /> : <Play size={18} />}</button>
            <button className="btn btn-outline btn-icon" type="button" onClick={() => step(1)} disabled={!n} aria-label="Next photo" title="Next photo (right arrow)"><SkipForward size={16} /></button>
            <Segmented label="Playback speed" value={p.speed} onChange={p.setSpeed} options={SPEEDS.map(s => ({ ...s }))} />
          </div>
          <Segmented label="Image mode" value={p.mode} onChange={p.setMode} options={MODES} />
        </div>
        <p className="hint">{MODE_HINT[p.mode]}</p>
        {p.status && <p className="hint status" aria-live="polite">{p.status}</p>}
      </div>
    </div>
  );
}
