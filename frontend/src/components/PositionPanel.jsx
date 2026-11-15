import React, { useEffect, useState } from "react";
import { api, json } from "../api.js";

const num = (s) => (s.trim() === "" || isNaN(+s) ? null : +s);

export default function PositionPanel({ sel, onChanged, setError }) {
  const [ra, setRa] = useState("");
  const [dec, setDec] = useState("");
  const [crop, setCrop] = useState("200");

  // show what is stored whenever the dataset or its centre changes
  useEffect(() => {
    setRa(sel?.centre ? String(+sel.centre[0].toFixed(5)) : "");     // 5 decimals = 0.04 arcsec
    setDec(sel?.centre ? String(+sel.centre[1].toFixed(5)) : "");
    setCrop(String(sel?.crop ?? 200));
  }, [sel?.id, sel?.centre?.[0], sel?.centre?.[1], sel?.crop]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!sel) return null;

  const rv = num(ra), dv = num(dec);
  const valid = rv !== null && dv !== null && rv >= 0 && rv <= 360 && dv >= -90 && dv <= 90;
  const changed = !sel.centre || rv !== +sel.centre[0].toFixed(5) || dv !== +sel.centre[1].toFixed(5);

  const send = async (body) => {
    try { await api(`/api/datasets/${sel.id}`, json("PATCH", body)); onChanged(); }
    catch (e) { setError(e.message); }
  };
  // pasting "133.79 -7.24" or "133.79, -7.24" into either box fills both
  const paste = (e) => {
    const parts = e.clipboardData.getData("text").trim().split(/[\s,;]+/);
    if (parts.length === 2 && parts.every((p) => p !== "" && !isNaN(+p))) {
      e.preventDefault(); setRa(parts[0]); setDec(parts[1]);
    }
  };
  const enter = (e) => e.key === "Enter" && valid && changed && send({ ra: rv, dec: dv });

  let status;
  if (sel.centre) status = <>Set by you: RA {sel.centre[0].toFixed(4)}, Dec {sel.centre[1].toFixed(4)}</>;
  else if (sel.centre_is_auto) status = <>Automatic: the middle of the first image (RA {sel.effective_centre[0].toFixed(4)}, Dec {sel.effective_centre[1].toFixed(4)})</>;
  else status = <>None set. Big images stay hidden until you set one.</>;

  return (
    <div className="card">
      <h2>2. Sky position</h2>
      <div className="grid2">
        <div><label>RA (degrees)</label><input type="text" inputMode="decimal" value={ra} placeholder="0 to 360"
          onChange={(e) => setRa(e.target.value)} onPaste={paste} onKeyDown={enter} /></div>
        <div><label>Dec (degrees)</label><input type="text" inputMode="decimal" value={dec} placeholder="-90 to 90"
          onChange={(e) => setDec(e.target.value)} onPaste={paste} onKeyDown={enter} /></div>
      </div>
      <div className="row" style={{ marginTop: 8 }}>
        <button className="primary" disabled={!valid || !changed} onClick={() => send({ ra: rv, dec: dv })}>Apply</button>
        <button disabled={!sel.centre} onClick={() => send({ clear_centre: true })}>Clear</button>
        <span style={{ flex: 1 }} />
        <span className="muted small">Window</span>
        <input type="text" inputMode="numeric" style={{ width: 64, flex: "0 0 64px" }} value={crop}
          onChange={(e) => setCrop(e.target.value)}
          onBlur={() => num(crop) && +crop !== sel.crop && send({ crop: Math.round(+crop) })}
          onKeyDown={(e) => e.key === "Enter" && e.target.blur()} title="Window size in pixels, used to crop big images" />
        <span className="muted small">px</span>
      </div>
      <div className="small muted" style={{ marginTop: 8 }}>{status}</div>
      {!valid && (ra !== "" || dec !== "") && <div className="small" style={{ color: "var(--warn)" }}>Enter RA 0 to 360 and Dec -90 to 90, in decimal degrees.</div>}
      <div className="small muted" style={{ marginTop: 4 }}>
        Change it as often as you like. Your files are never altered. You can paste "RA, Dec" into either box.
      </div>
    </div>
  );
}
