import { useEffect, useState } from "react";
import { Crosshair, Shuffle } from "lucide-react";
import type { Detector, Target } from "../api";
import { DESCRIBE, DETECTORS, FOVS, KIND } from "../lib";
import { Section, Segmented } from "./Bits";

export function TargetList({ targets, activeId, onPick }: { targets: Target[] | null; activeId: string | null; onPick: (t: Target) => void }) {
  return (
    <Section title="Start with a famous moving star">
      {!targets ? (
        <div className="targets" aria-busy="true">
          {Array.from({ length: 6 }, (_, i) => <div key={i} className="target skeleton" />)}
        </div>
      ) : (
        <div className="targets">
          {targets.map(t => {
            const [kind, cls] = KIND[t.id] ?? ["Star", "st"];
            return (
              <button key={t.id} type="button" className="target" aria-pressed={t.id === activeId} onClick={() => onPick(t)}>
                <span className="target-name">{t.name}</span>
                <span className={`kind ${cls}`}>{kind}</span>
                <span className="target-desc">{DESCRIBE[t.id] ?? ""}</span>
              </button>
            );
          })}
        </div>
      )}
    </Section>
  );
}

export function SpotForm({ ra, dec, onGo, onRandom }: { ra: number | null; dec: number | null; onGo: (ra: number, dec: number) => void; onRandom: () => void }) {
  const [r, setR] = useState(ra?.toString() ?? "");
  const [d, setD] = useState(dec?.toString() ?? "");
  useEffect(() => { setR(ra?.toString() ?? ""); setD(dec?.toString() ?? ""); }, [ra, dec]);
  const rn = parseFloat(r), dn = parseFloat(d);
  const valid = r !== "" && d !== "" && rn >= 0 && rn < 360 && dn >= -90 && dn <= 90;
  return (
    <Section title="Or go to any spot in the sky">
      <form className="spot-form" onSubmit={e => { e.preventDefault(); if (valid) onGo(rn, dn); }}>
        <div className="two">
          <label className="field"><span>RA (degrees)</span>
            <input className="input num" inputMode="decimal" value={r} onChange={e => setR(e.target.value)} placeholder="0 to 360" />
          </label>
          <label className="field"><span>Dec (degrees)</span>
            <input className="input num" inputMode="decimal" value={d} onChange={e => setD(e.target.value)} placeholder="-90 to 90" />
          </label>
        </div>
        <p className="hint">RA and Dec are the sky's longitude and latitude. You can also type a star name in the search box.</p>
        <button className="btn btn-primary" type="submit" disabled={!valid}><Crosshair size={16} />Show this spot</button>
        <button className="btn btn-outline" type="button" onClick={onRandom} title="Somewhere away from the Milky Way that nobody may have looked at closely">
          <Shuffle size={16} />Explore a random spot
        </button>
      </form>
    </Section>
  );
}

export function FovPicker({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <Section title="How much sky to show">
      <Segmented label="How much sky to show" value={value} onChange={onChange} className="full"
        options={FOVS.map(f => ({ v: f.v, label: f.label, title: f.title }))} />
      <p className="hint">Wide catches faster movers but takes longer to load. Medium is a tenth of the full Moon's width.</p>
    </Section>
  );
}

export function DetectorStrip({ value, onChange, bestFor }: { value: Detector; onChange: (d: Detector) => void; bestFor: Target | null }) {
  return (
    <Section title="Infrared color">
      <div className="strip" role="radiogroup" aria-label="SPHEREx detector">
        {DETECTORS.map(d => (
          <button key={d.id} type="button" role="radio" aria-checked={d.id === value} style={{ ["--c" as string]: d.color }}
            title={`${d.id}: ${d.band} micrometres`} onClick={() => onChange(d.id)}>
            <b>{d.id}</b><span>{d.mid} µm</span>
          </button>
        ))}
      </div>
      <div className="strip-scale"><span>Warmer stars stand out</span><span>Cold objects glow</span></div>
      <p className="hint">
        {bestFor && bestFor.detector !== value
          ? `${bestFor.name} shows up best in ${bestFor.detector}.`
          : "SPHEREx has six detectors, each seeing a different slice of infrared light. Cold brown dwarfs (failed stars) glow at the right end."}
      </p>
    </Section>
  );
}
