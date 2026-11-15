import React, { useCallback, useEffect, useState } from "react";
import { api, loadImage } from "./api.js";
import DatasetPanel from "./components/DatasetPanel.jsx";
import PositionPanel from "./components/PositionPanel.jsx";
import ImagesPanel from "./components/ImagesPanel.jsx";
import ViewPanel from "./components/ViewPanel.jsx";
import Viewer from "./components/Viewer.jsx";
import Guide from "./components/Guide.jsx";

function useDebounced(value, ms) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

export default function App() {
  const params = new URLSearchParams(location.search);
  const [tab, setTab] = useState("viewer");
  const [datasets, setDatasets] = useState([]);
  const [selId, setSelId] = useState(params.get("ds") || "");
  const [band, setBand] = useState(params.get("band") || "");
  const [mode, setMode] = useState(params.get("mode") || "flip");
  const [sens, setSens] = useState(4);
  const [error, setError] = useState("");
  const [view, setView] = useState({ frames: [], imgs: [], still: null, busy: false });
  const [moverState, setMoverState] = useState({ movers: [], note: "", busy: false, nFrames: 0 });
  const [selectedMover, setSelectedMover] = useState(-1);

  const sel = datasets.find((d) => d.id === selId);
  const nsigma = useDebounced(sens, 400);

  // reload the list of datasets (and optionally pick one)
  const refresh = useCallback(async (pick) => {
    try {
      const list = await api("/api/datasets");
      setDatasets(list);
      setSelId((cur) => pick || (list.some((d) => d.id === cur) ? cur : list[0]?.id || ""));
    } catch (e) {
      setError(e.message);
    }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  // keep the band valid for the chosen dataset
  useEffect(() => {
    const bands = sel ? Object.keys(sel.bands) : [];
    if (bands.length && !bands.includes(band)) setBand(bands[0]);
    if (!bands.length && band) setBand("");
  }, [sel, band]);

  useEffect(() => {
    if (selId) history.replaceState(null, "", `?ds=${selId}&band=${band}&mode=${mode}`);
  }, [selId, band, mode]);

  // anything that changes what the pictures show
  const dataKey = sel ? [sel.id, band, sel.n_ok, sel.n_files, sel.centre, sel.crop].join("|") : "";

  // 1) pictures
  useEffect(() => {
    let cancelled = false;
    setSelectedMover(-1);
    if (!sel || !band || sel.n_ok === 0) {
      setView({ frames: [], imgs: [], still: null, busy: false });
      return;
    }
    setView((v) => ({ ...v, busy: true }));
    (async () => {
      try {
        const q = `?band=${encodeURIComponent(band)}`;
        const { frames } = await api(`/api/datasets/${sel.id}/frames${q}`);
        let imgs = [], still = null;
        if (mode === "flip") imgs = await Promise.all(frames.map((f) => loadImage(f.png_url)));
        else if (frames.length >= 2) still = await loadImage(`/api/datasets/${sel.id}/${mode === "composite" ? "composite" : "difference"}.png${q}&t=${Date.now()}`);
        if (!cancelled) setView({ frames, imgs, still, busy: false });
      } catch (e) {
        if (!cancelled) { setError(e.message); setView((v) => ({ ...v, busy: false })); }
      }
    })();
    return () => { cancelled = true; };
  }, [dataKey, mode]); // eslint-disable-line react-hooks/exhaustive-deps

  // 2) movers (slower, so shown after the picture)
  useEffect(() => {
    let cancelled = false;
    setSelectedMover(-1);
    if (!sel || !band || sel.n_ok === 0) { setMoverState({ movers: [], note: "", busy: false, nFrames: 0 }); return; }
    setMoverState((m) => ({ ...m, busy: true, note: "" }));
    api(`/api/datasets/${sel.id}/movers?band=${encodeURIComponent(band)}&nsigma=${nsigma}`)
      .then((d) => !cancelled && setMoverState({ movers: d.movers, note: d.note || "", busy: false, nFrames: d.n_frames }))
      .catch((e) => !cancelled && setMoverState({ movers: [], note: e.message, busy: false, nFrames: 0 }));
    return () => { cancelled = true; };
  }, [dataKey, nsigma]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      <div className="topbar">
        <h1>Mover Spotter</h1>
        <div className="tabs">
          <button className={tab === "viewer" ? "on" : ""} onClick={() => setTab("viewer")}>Viewer</button>
          <button className={tab === "guide" ? "on" : ""} onClick={() => setTab("guide")}>Where do I get images?</button>
        </div>
      </div>
      {error && (
        <div className="notice bad" style={{ margin: "10px 18px" }}>
          {error} <button className="link" onClick={() => setError("")}>dismiss</button>
        </div>
      )}
      {tab === "guide" ? (
        <Guide onBack={() => setTab("viewer")} />
      ) : (
        <div className="layout">
          <div className="side">
            <DatasetPanel datasets={datasets} selId={selId} onSelect={setSelId} onChanged={refresh} setError={setError} />
            <PositionPanel sel={sel} onChanged={() => refresh()} setError={setError} />
            <ImagesPanel sel={sel} onChanged={() => refresh()} setError={setError} onGuide={() => setTab("guide")} />
            <ViewPanel sel={sel} band={band} setBand={setBand} mode={mode} setMode={setMode} sens={sens} setSens={setSens} />
          </div>
          <Viewer
            sel={sel} view={view} mode={mode} moverState={moverState}
            selectedMover={selectedMover} onSelectMover={setSelectedMover}
            onGuide={() => setTab("guide")}
          />
        </div>
      )}
    </>
  );
}
