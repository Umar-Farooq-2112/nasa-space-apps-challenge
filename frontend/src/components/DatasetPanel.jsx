import React, { useState } from "react";
import { api, json } from "../api.js";

export default function DatasetPanel({ datasets, selId, onSelect, onChanged, setError }) {
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");

  const create = async () => {
    try {
      const d = await api("/api/datasets", json("POST", { name: name || "My dataset" }));
      setCreating(false);
      setName("");
      await onChanged(d.id);
    } catch (e) { setError(e.message); }
  };
  const remove = async () => {
    if (!selId || !confirm("Delete this dataset and all its images?")) return;
    try { await api(`/api/datasets/${selId}`, { method: "DELETE" }); await onChanged(); }
    catch (e) { setError(e.message); }
  };

  return (
    <div className="card">
      <h2>1. Dataset</h2>
      <div className="row">
        <select value={selId} onChange={(e) => onSelect(e.target.value)}>
          {datasets.length === 0 && <option value="">(none yet)</option>}
          {datasets.map((d) => <option key={d.id} value={d.id}>{d.name} ({d.n_files} files)</option>)}
        </select>
        <button onClick={() => setCreating((c) => !c)}>New</button>
        <button onClick={remove} disabled={!selId}>Delete</button>
      </div>
      {creating && (
        <div className="row" style={{ marginTop: 8 }}>
          <input type="text" autoFocus placeholder="Name, e.g. my brown dwarf" value={name}
            onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && create()} />
          <button className="primary" onClick={create}>Create</button>
        </div>
      )}
      {datasets.length === 0 && !creating && (
        <div className="muted small" style={{ marginTop: 8 }}>
          A dataset holds the images of one sky patch. Press <b>New</b> to start.
        </div>
      )}
    </div>
  );
}
