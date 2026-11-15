import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowRight, Link2, Search } from "lucide-react";
import { frameUrl, getTargets, resolveName, type Detector, type Mode, type Spot, type Target } from "./api";
import { DETECTORS, downloadCsv, isTargetHere, mjdDate, randomSpot, type Catalog } from "./lib";
import { reduceMotion, useImages, useSky } from "./hooks";
import { Logo, Spinner } from "./components/Bits";
import { DetectorStrip, FovPicker, SpotForm, TargetList } from "./components/Sidebar";
import { Viewer } from "./components/Viewer";
import { Chart, FrameMeta, MoverList } from "./components/Results";

interface View { ra: number; dec: number; name: string; catalog: Catalog | null }

const targetsPromise = getTargets();

function fromUrl() {
  const p = new URLSearchParams(location.search);
  const ra = parseFloat(p.get("ra") ?? ""), dec = parseFloat(p.get("dec") ?? "");
  const fov = ["0.05", "0.1", "0.2"].includes(p.get("fov") ?? "") ? p.get("fov")! : "0.1";
  const det = (DETECTORS.some(d => d.id === p.get("detector")) ? p.get("detector") : "D3") as Detector;
  const mode = (["diff", "deep"].includes(p.get("mode") ?? "") ? p.get("mode") : "sky") as Mode;
  const view = isNaN(ra) || isNaN(dec) ? null : { ra, dec, name: p.get("name") ?? "", catalog: null };
  return { view, fov, det, mode };
}

export default function App() {
  const init = useMemo(fromUrl, []);
  const [targets, setTargets] = useState<Target[] | null>(null);
  const [view, setView] = useState<View | null>(init.view);
  const [fov, setFov] = useState(init.fov);
  const [det, setDet] = useState<Detector>(init.det);
  const [mode, setMode] = useState<Mode>(init.mode);
  const [speed, setSpeed] = useState("350");
  const [idx, setIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [selected, setSelected] = useState(-1);
  const [chart, setChart] = useState<"time" | "wave">("time");
  const [max, setMax] = useState(false);
  const [toast, setToast] = useState<{ msg: string; id: number } | null>(null);
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [starting, setStarting] = useState(false);

  const say = useCallback((msg: string) => setToast({ msg, id: Date.now() }), []);
  useEffect(() => { if (!toast) return; const t = setTimeout(() => setToast(null), 2600); return () => clearTimeout(t); }, [toast]);

  useEffect(() => {
    targetsPromise.then(ts => {
      setTargets(ts);
      // a shared link to a preset: name it and compare its movers with the catalog
      setView(v => {
        const t = v && ts.find(t => isTargetHere(t, v.ra, v.dec));
        return v && t ? { ...v, name: v.name || t.name, catalog: { pmra: t.pmra, pmdec: t.pmdec } } : v;
      });
    }).catch(() => say("Could not load the star list. Search by name still works."));
  }, [say]);

  const spot: Spot | null = useMemo(() => (view ? { ra: view.ra, dec: view.dec, fov, det } : null), [view?.ra, view?.dec, fov, det]);
  const sky = useSky(spot);
  const n = sky.frames.length;
  const urls = useMemo(() => sky.frames.map(f => frameUrl(f, mode, n)), [sky.frames, mode, n]);
  const imgs = useImages(urls);
  const loaded = imgs.filter(Boolean).length;
  const movers = sky.movers?.movers ?? [];
  const activeTarget = view && targets ? targets.find(t => isTargetHere(t, view.ra, view.dec)) ?? null : null;

  // new spot: start over at the first photo
  useEffect(() => { setIdx(0); setPlaying(false); setSelected(-1); }, [spot]);
  useEffect(() => { if (idx >= n && n) setIdx(0); }, [n, idx]);

  // autoplay once the photos of a new spot are in
  const autoplayed = useRef("");
  useEffect(() => {
    const key = spot ? JSON.stringify(spot) : "";
    if (key && n > 1 && loaded === n && autoplayed.current !== key && !reduceMotion) { autoplayed.current = key; setPlaying(true); }
  }, [spot, n, loaded]);

  useEffect(() => {
    if (!playing || n < 2) return;
    const t = setInterval(() => setIdx(i => (i + 1) % n), +speed);
    return () => clearInterval(t);
  }, [playing, n, speed]);

  // the URL always describes the current view, so it can be shared or embedded
  useEffect(() => {
    if (!view) return;
    const p = new URLSearchParams({ ra: String(view.ra), dec: String(view.dec), fov, detector: det });
    if (mode !== "sky") p.set("mode", mode);
    if (view.name) p.set("name", view.name);
    history.replaceState(null, "", `?${p}`);
  }, [view, fov, det, mode]);

  useEffect(() => {
    if (!max) return;
    const prev = document.body.style.overflow; document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, [max]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).closest("input, textarea, select")) return;
      if (e.key === "Escape" && max) setMax(false);
      if (!n) return;
      if (e.code === "Space") { e.preventDefault(); setPlaying(p => !p); }
      else if (e.key === "ArrowLeft") { setPlaying(false); setIdx(i => (i - 1 + n) % n); }
      else if (e.key === "ArrowRight") { setPlaying(false); setIdx(i => (i + 1) % n); }
      else if (e.key === "d" || e.key === "D") setMode(m => (m === "diff" ? "sky" : "diff"));
      else if (e.key === "f" || e.key === "F") setMax(m => !m);
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [n, max]);

  function pickTarget(t: Target) {
    setView({ ra: t.ra, dec: t.dec, name: t.name, catalog: { pmra: t.pmra, pmdec: t.pmdec } });
    setDet(t.detector);
  }

  async function startTour() {
    setStarting(true);
    try { const ts = await targetsPromise; const t = ts.find(t => t.id === "barnards_star"); if (t) pickTarget(t); }
    catch { say("The server is not answering yet. Try again in a moment."); }
    finally { setStarting(false); }
  }

  async function onSearch(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim(); if (!q) return;
    const nums = q.replace(/,/g, " ").split(/\s+/).map(Number);
    if (nums.length === 2 && nums.every(x => !isNaN(x))) {
      if (nums[0] < 0 || nums[0] >= 360 || nums[1] < -90 || nums[1] > 90) { say("RA must be 0 to 360 and Dec -90 to 90."); return; }
      setView({ ra: nums[0], dec: nums[1], name: "", catalog: null }); return;
    }
    setSearching(true);
    try {
      const d = await resolveName(q);
      setView({ ra: d.ra, dec: d.dec, name: q, catalog: { pmra: d.pmra, pmdec: d.pmdec } });
      say(d.pm_mas_yr > 100 ? `${q} moves ${(d.pm_mas_yr / 1000).toFixed(1)} arcseconds per year. Position set for 2026.` : `Found ${q}.`);
    } catch (err) { say((err as Error).message); }
    finally { setSearching(false); }
  }

  async function share() {
    try { await navigator.clipboard.writeText(location.href); say("Link copied. Anyone with it sees this view."); }
    catch { say("Copy this page's address to share the view."); }
  }

  // what the plate shows before (or instead of) photos
  const s = sky.status, busy = !s || s.state === "searching" || s.state === "downloading";
  let overlay: React.ReactNode = null;
  if (!view) overlay = (
    <div className="intro">
      <h3>Some dots in the night sky move. Find them.</h3>
      <p>NASA's SPHEREx space telescope photographs the whole sky in infrared every six months. Charon lines up its photos of one spot and plays them like a flip-book.</p>
      <ol>
        <li><span><b>Pick a star</b> on the left, or search any name or position.</span></li>
        <li><span><b>Watch a year of real photos</b> of that patch of sky, oldest to newest.</span></li>
        <li><span><b>See what moves.</b> Anything that shifts is circled and checked against star catalogs. Nearby stars and brown dwarfs give themselves away like this, and so might an unknown planet.</span></li>
      </ol>
      <button className="btn btn-light" type="button" onClick={startTour} disabled={starting}>
        {starting ? <Spinner small /> : null}Show me Barnard's Star, the fastest star in the sky
      </button>
    </div>
  );
  else if (sky.error && !n) overlay = <p>{sky.error}</p>;
  else if (!n && busy) {
    const pct = s?.total ? Math.round((100 * n) / s.total) : 6;
    overlay = (
      <div className="loading">
        <Spinner />
        <p>{s?.state === "downloading" ? `Getting photos from NASA: ${n} of ${s.total}` : "Finding every SPHEREx photo of this spot..."}</p>
        <div className="progress"><i style={{ width: `${pct}%` }} /></div>
        <p className="why">A spot nobody has opened before takes up to a minute: each photo is cut out of a 65 MB NASA file, then kept so the next visit is instant.</p>
      </div>
    );
  }
  else if (!n) overlay = <p>SPHEREx has no {det} photos of this spot yet. Try another infrared color or another spot.</p>;
  else if (!imgs[idx] && !imgs.some(Boolean)) overlay = <div className="loading"><Spinner /><p>Loading photos: {loaded} of {n}</p></div>;

  const status = n && busy ? `Getting photos from NASA: ${n} of ${s?.total ?? "?"}. The movie grows as they arrive.`
    : n && loaded < n ? `Loading photos: ${loaded} of ${n}` : sky.error ?? "";
  const coords = view ? `RA ${view.ra.toFixed(4)}°, Dec ${view.dec.toFixed(4)}°` : "";
  const live = s?.available && s.first_mjd && s.last_mjd
    ? `SPHEREx took ${s.available} photos of this spot between ${mjdDate(s.first_mjd)} and ${mjdDate(s.last_mjd)}; showing ${s.total} spread over that time.`
      + (sky.newest ? ` NASA's newest release goes up to ${mjdDate(sky.newest)}, and SPHEREx returns to each spot about every six months.` : "")
    : "";

  return (
    <>
      <header className="topbar">
        <div className="bar">
          <a className="brand" href="/" aria-label="Charon home"><Logo /><b>Charon</b><span>find what moves in NASA's SPHEREx sky</span></a>
          <form className="search" role="search" onSubmit={onSearch}>
            <Search size={16} className="search-icon" aria-hidden="true" />
            <input className="input" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search a star by name, or type RA Dec in degrees" aria-label="Star name or coordinates" autoComplete="off" />
            <button className="btn btn-primary" type="submit" disabled={searching}>{searching ? <Spinner small /> : <ArrowRight size={16} />}Search</button>
          </form>
          <button className="btn btn-outline" type="button" onClick={share} disabled={!view} title="Copy a link to this view"><Link2 size={16} />Copy link</button>
        </div>
      </header>

      <main className="sheet">
        <aside className="col left" aria-label="Choose what to look at">
          <TargetList targets={targets} activeId={activeTarget?.id ?? null} onPick={pickTarget} />
          <SpotForm ra={view?.ra ?? null} dec={view?.dec ?? null} onGo={(ra, dec) => setView({ ra, dec, name: "", catalog: null })}
            onRandom={() => { const r = randomSpot(); setView({ ...r, name: "Random spot", catalog: null }); }} />
          <FovPicker value={fov} onChange={setFov} />
          <DetectorStrip value={det} onChange={setDet} bestFor={activeTarget} />
        </aside>

        <section className="col center" aria-label="Sky viewer">
          <div className="view-head">
            <h1>{view ? view.name || "Custom spot" : "See the sky change over a year"}</h1>
            {view && <span className="coords num">{coords}</span>}
          </div>
          {live && <p className="live"><i aria-hidden="true" />Live NASA data. {live}</p>}
          {movers.length > 0 && (
            <div className="legend">
              <span><i aria-hidden="true" />Circle: an object the tracker found moving</span>
              <span><i className="trail" aria-hidden="true" />Line: the path it took</span>
              <span>Everything else stays still</span>
            </div>
          )}
          <Viewer title={view?.name || "Custom spot"} coords={coords} frames={sky.frames} imgs={imgs} idx={Math.min(idx, Math.max(n - 1, 0))} setIdx={setIdx}
            playing={playing} setPlaying={setPlaying} speed={speed} setSpeed={setSpeed} mode={mode} setMode={setMode}
            movers={movers} scale={sky.movers?.scale ?? 12} selected={selected} onSelect={k => setSelected(sel => (sel === k ? -1 : k))}
            overlay={overlay} status={status} max={max} setMax={setMax} />
        </section>

        <aside className="col right" aria-label="Results">
          <MoverList movers={movers} loading={sky.moversLoading} note={sky.movers?.note} nFrames={n} selected={selected}
            onSelect={k => setSelected(sel => (sel === k ? -1 : k))} catalog={view?.catalog ?? null} ra={view?.ra ?? 0} dec={view?.dec ?? 0} hasSpot={!!view}
            onExport={() => { downloadCsv(movers, sky.frames.map(f => f.date), `charon_${view?.ra}_${view?.dec}_${det}.csv`); say("Results downloaded."); }} />
          {selected >= 0 && movers[selected] && n > 0 && (
            <Chart mover={movers[selected]} k={selected} frames={sky.frames} idx={idx} kind={chart} setKind={setChart} />
          )}
          <FrameMeta frame={sky.frames[idx]} />
          <section className="section about">
            <p className="hint">Keys: <kbd>Space</kbd> play, <kbd>←</kbd> <kbd>→</kbd> step, <kbd>D</kbd> changes only, <kbd>F</kbd> full view.</p>
            <p className="hint">Named after Charon, Pluto's largest moon. In 1978 James Christy found it by noticing a bump on Pluto's image that moved from photo to photo. This app does the same with NASA's SPHEREx telescope.</p>
          </section>
        </aside>
      </main>

      <footer className="foot">
        <p><b>How we know a find is real.</b> Each photo is aligned to the same north-up grid using its own sky coordinates (WCS). Every star is located in every photo, small pointing shifts are removed using the stars that stay still, and only objects that move in a straight line across most photos are kept. Each find gets a speed, a direction, an error bar and a confidence, and is compared with the Gaia catalog via SIMBAD. Tested on eight known nearby stars and brown dwarfs: all six fast movers found, no false movers on the two variable stars.</p>
        <p><b>Data and credits.</b> Images: NASA SPHEREx (JPL/Caltech), from the NASA/IPAC Infrared Science Archive (IRSA) and its open copy on AWS. Star positions and motions: ESA Gaia via SIMBAD and the CDS Sesame name resolver. Software: Python, FastAPI, Astropy, NumPy, SciPy, Pillow, React. Fonts: Newsreader and Geist (SIL Open Font License). Built for the NASA Space Apps Challenge 2026 with help from AI coding tools (Claude Code).</p>
      </footer>

      <div className={toast ? "toast show" : "toast"} role="status" aria-live="polite">{toast?.msg}</div>
    </>
  );
}
