import { Check, Download, TriangleAlert } from "lucide-react";
import type { Frame, Mover } from "../api";
import { fitsUrl } from "../api";
import { catalogMatch, coinKm, compass, confidence, DETECTORS, fmtDate, type Catalog } from "../lib";
import { Section, Segmented, Spinner } from "./Bits";

export function MoverList({ movers, loading, note, nFrames, selected, onSelect, catalog, ra, dec, onExport, hasSpot }: {
  movers: Mover[]; loading: boolean; note?: string; nFrames: number; selected: number; onSelect: (k: number) => void;
  catalog: Catalog | null; ra: number; dec: number; onExport: () => void; hasSpot: boolean;
}) {
  const exportBtn = movers.length > 0 && (
    <button className="btn btn-outline btn-sm" type="button" onClick={onExport} title="Every measured position, for scientists and citizen scientists">
      <Download size={14} />CSV
    </button>
  );
  return (
    <Section title="What moved" aside={exportBtn}>
      {loading ? (
        <p className="empty"><Spinner small />Checking {nFrames} photos for anything that moves. About 10 seconds the first time.</p>
      ) : !hasSpot ? (
        <p className="empty">Pick a star and every photo is checked for things that move.</p>
      ) : !movers.length ? (
        <p className="empty">{note ?? (nFrames ? "Nothing here moved enough to measure in a year. That is normal: almost every star is too far away to visibly shift." : "Waiting for the photos.")}</p>
      ) : (
        <div className="movers">
          {movers.map((m, k) => {
            const match = catalogMatch(m, catalog, ra, dec);
            return (
              <button key={k} type="button" className="mover" aria-pressed={k === selected} onClick={() => onSelect(k)}>
                <span className="mover-head">
                  <i className="dot" aria-hidden="true">{k + 1}</i>
                  <span><b>Object {k + 1} is moving {compass(m.pa_deg)}</b><small>Found in {m.n_detections} of {m.points.length} photos</small></span>
                </span>
                <span className="verdict num">{m.rate_arcsec_per_year.toFixed(2)} ± {m.rate_err_arcsec_per_year.toFixed(2)} arcseconds per year</span>
                <span className="why">Like a coin seen from {coinKm(m.rate_arcsec_per_year)} km away sliding its own width in a year. Tiny, but SPHEREx can measure it, and only nearby objects move this fast.</span>
                <dl className="stats num">
                  <dt>Direction</dt><dd>{m.pa_deg.toFixed(0)}° east of north</dd>
                  <dt>Moved</dt><dd>{m.displacement_arcsec.toFixed(1)}″ in {Math.round(m.span_days)} days</dd>
                  <dt>Track fit error</dt><dd>{m.fit_rms_arcsec.toFixed(2)}″</dd>
                  <dt>Confidence</dt><dd>{confidence(m.significance)} ({m.significance.toFixed(0)}σ)</dd>
                </dl>
                {match && (
                  <span className={match.good ? "match" : "match off"}>
                    {match.good ? <Check size={15} /> : <TriangleAlert size={15} />}
                    <span>{match.good ? "Matches" : "Compare with"} the Gaia catalog: {match.rate.toFixed(2)}″ per year toward {match.pa.toFixed(0)}°.
                      Speed within {match.dRate.toFixed(0)}%, direction within {match.dPa.toFixed(0)}°.</span>
                  </span>
                )}
              </button>
            );
          })}
          <p className="hint">Click an object, or its circle on the photo, to see its brightness and spectrum.</p>
        </div>
      )}
    </Section>
  );
}

export function Chart({ mover, k, frames, idx, kind, setKind }: {
  mover: Mover; k: number; frames: Frame[]; idx: number; kind: "time" | "wave"; setKind: (v: "time" | "wave") => void;
}) {
  const wave = kind === "wave";
  const pts = mover.points.filter(p => p.flux !== null && (!wave || p.wavelength_um))
    .map(p => ({ x: wave ? p.wavelength_um! : frames[p.frame]?.mjd ?? 0, v: p.flux!, d: p.detected, f: p.frame }));
  const xs = pts.map(p => p.x), vs = pts.map(p => p.v);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), v0 = Math.min(0, ...vs), v1 = Math.max(...vs);
  const X = (x: number) => 40 + ((x - x0) / (x1 - x0 || 1)) * 250, Y = (v: number) => 126 - ((v - v0) / (v1 - v0 || 1)) * 108;
  const cur = pts.find(p => p.f === idx);
  const sorted = [...pts].sort((a, b) => a.x - b.x);
  const trend = wave && sorted.length > 2 ? "M" + sorted.map((p, i) => {
    const w = sorted.slice(Math.max(0, i - 1), i + 2);
    return `${X(p.x).toFixed(1)},${Y(w.reduce((a, q) => a + q.v, 0) / w.length).toFixed(1)}`;
  }).join("L") : "";
  const lab = wave ? [`${x0.toFixed(2)} µm`, `${x1.toFixed(2)} µm`] : [fmtDate(frames[0].date), fmtDate(frames[frames.length - 1].date)];
  return (
    <Section title={wave ? `Spectrum of object ${k + 1}` : `Brightness of object ${k + 1}`}
      aside={<Segmented label="Chart" value={kind} onChange={setKind} className="sm" options={[{ v: "time", label: "Time" }, { v: "wave", label: "Spectrum" }]} />}>
      {pts.length ? (
        <svg className="chart" viewBox="0 0 300 150" role="img" aria-label={wave ? "Spectrum of the selected object" : "Brightness of the selected object over time"}>
          <line x1="40" y1="132" x2="290" y2="132" stroke="#DCE2EA" /><line x1="40" y1="12" x2="40" y2="132" stroke="#DCE2EA" />
          {cur && <line x1={X(cur.x)} y1="12" x2={X(cur.x)} y2="132" stroke="#8A95AA" strokeDasharray="3 3" />}
          {trend && <path d={trend} fill="none" stroke="#D6336C" strokeOpacity=".45" strokeWidth="2" />}
          {pts.map((q, i) => <circle key={i} cx={X(q.x)} cy={Y(q.v)} r={q.f === idx ? 4.5 : 3.4} fill={q.d ? "#D6336C" : "#fff"} fillOpacity=".9" stroke="#D6336C" />)}
          <text x="40" y="146" fontSize="10" fill="#6B7790">{lab[0]}</text>
          <text x="290" y="146" fontSize="10" fill="#6B7790" textAnchor="end">{lab[1]}</text>
          <text x="35" y="18" fontSize="10" fill="#6B7790" textAnchor="end">bright</text>
          <text x="35" y="130" fontSize="10" fill="#6B7790" textAnchor="end">faint</text>
        </svg>
      ) : <p className="empty">No brightness measurements for this object.</p>}
      <p className="hint">
        {wave ? "SPHEREx sees a different wavelength at each spot on its detector, so a year of photos builds up a spectrum. Dips mark molecules such as water and methane."
          : "Filled dots: detected. Open dots: measured where the track predicts. Sky light subtracted."}
      </p>
    </Section>
  );
}

export function FrameMeta({ frame }: { frame: Frame | undefined }) {
  const d = frame && DETECTORS.find(x => x.id === frame.detector);
  return (
    <Section title="This photo">
      {frame ? (
        <dl className="meta num">
          <dt>Taken</dt><dd>{frame.date.replace("T", " ").slice(0, 16)} UTC</dd>
          <dt>Detector</dt><dd>{frame.detector}, {d?.band} µm</dd>
          <dt>SPHEREx image</dt><dd>{frame.file.split("_").slice(3, 7).join(" ")}</dd>
          <dt>Raw data</dt><dd><a href={fitsUrl(frame)} download>Download FITS</a></dd>
        </dl>
      ) : <p className="empty">Details of each photo show here.</p>}
    </Section>
  );
}
