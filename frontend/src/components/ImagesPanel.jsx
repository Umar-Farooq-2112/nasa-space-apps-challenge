import React, { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

const STATUS_TEXT = {
  ok: "ok",
  needs_centre: "needs RA/Dec",
  outside: "outside position",
  error: "unreadable",
};

export default function ImagesPanel({ sel, onChanged, setError, onGuide }) {
  const [files, setFiles] = useState([]);
  const [log, setLog] = useState([]);
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const input = useRef();

  const key = sel ? [sel.id, sel.n_files, sel.centre, sel.crop].join("|") : "";
  useEffect(() => {
    if (!sel) { setFiles([]); return; }
    api(`/api/datasets/${sel.id}/files`).then(setFiles).catch((e) => setError(e.message));
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => setLog([]), [sel?.id]);

  if (!sel) return null;

  const upload = async (list) => {
    const all = [...list];
    if (!all.length) return;
    setBusy(true);
    setLog([]);
    for (let i = 0; i < all.length; i += 4) {                 // small batches so progress is visible
      const fd = new FormData();
      all.slice(i, i + 4).forEach((f) => fd.append("files", f));
      try {
        const j = await api(`/api/datasets/${sel.id}/files`, { method: "POST", body: fd });
        setLog((l) => [...l, ...j.results]);
      } catch (e) { setLog((l) => [...l, { name: "(batch)", ok: false, error: e.message }]); }
    }
    setBusy(false);
    onChanged();
  };

  const remove = async (file) => {
    try { await api(`/api/datasets/${sel.id}/files/${encodeURIComponent(file)}`, { method: "DELETE" }); onChanged(); }
    catch (e) { setError(e.message); }
  };

  const dropHandlers = {
    onDragOver: (e) => { e.preventDefault(); setOver(true); },
    onDragLeave: () => setOver(false),
    onDrop: (e) => { e.preventDefault(); setOver(false); upload(e.dataTransfer.files); },
  };

  return (
    <div className="card">
      <h2>3. Images</h2>
      <div className={"drop" + (over ? " over" : "")} {...dropHandlers}>
        {busy ? "Uploading..." : (
          <>Drop FITS files here, or <button className="link" onClick={() => input.current.click()}>choose files</button></>
        )}
        <input ref={input} type="file" multiple accept=".fits,.fit,.fts" hidden
          onChange={(e) => { upload(e.target.files); e.target.value = ""; }} />
      </div>
      {files.length === 0 && (
        <div className="small muted" style={{ marginTop: 8 }}>
          No images yet. Not sure where to get them? <button className="link" onClick={onGuide}>Open the guide</button>.
        </div>
      )}
      {log.length > 0 && (
        <div className="log" style={{ marginTop: 8 }}>
          {log.map((r, i) => r.ok
            ? <div key={i} className="ok">OK {r.name}: {r.band}, {r.date}</div>
            : <div key={i} className="err">Skipped {r.name}: {r.error}</div>)}
        </div>
      )}
      {files.length > 0 && (
        <>
          <div className="small muted" style={{ marginTop: 8 }}>
            {sel.n_ok} usable
            {sel.n_needs_centre > 0 && <> &middot; <span style={{ color: "var(--warn)" }}>{sel.n_needs_centre} need an RA/Dec above</span></>}
            {sel.n_outside > 0 && <> &middot; <span style={{ color: "var(--warn)" }}>{sel.n_outside} do not cover this position</span></>}
          </div>
          <div className="files">
            {files.map((f) => (
              <div className="f" key={f.file} title={f.error || f.orig}>
                <span className="name">{f.orig}</span>
                <span className="muted">{f.date ? f.date.slice(0, 10) : ""}</span>
                <span className="muted">{f.band || ""}</span>
                <span className={"chip " + f.status}>{STATUS_TEXT[f.status]}</span>
                <button className="icon" title="Remove this file" onClick={() => remove(f.file)}>&times;</button>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
