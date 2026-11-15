import { useEffect, useReducer, useState } from "react";
import { getFrames, getMovers, type FetchStatus, type Frame, type MoversResponse, type Spot } from "./api";

const sleep = (ms: number, signal: AbortSignal) =>
  new Promise<void>((res, rej) => {
    const t = setTimeout(res, ms);
    signal.addEventListener("abort", () => { clearTimeout(t); rej(new DOMException("aborted", "AbortError")); });
  });

export interface Sky {
  frames: Frame[]; status: FetchStatus | null; newest: number | null; error: string | null;
  movers: MoversResponse | null; moversLoading: boolean;
}
const EMPTY: Sky = { frames: [], status: null, newest: null, error: null, movers: null, moversLoading: false };

/** Frames for a spot (polling while NASA downloads run), then the tracker's movers. Restarts when the spot changes. */
export function useSky(spot: Spot | null): Sky {
  const [sky, setSky] = useState<Sky>(EMPTY);
  const key = spot ? `${spot.ra}|${spot.dec}|${spot.fov}|${spot.det}` : "";
  useEffect(() => {
    setSky(EMPTY);
    if (!spot) return;
    const ac = new AbortController();
    (async () => {
      try {
        let frames: Frame[] = [];
        for (;;) {
          const d = await getFrames(spot, ac.signal);
          const same = d.frames.length === frames.length && d.frames.every((f, i) => f.file === frames[i].file);
          if (!same) frames = d.frames;   // keep the array identity when nothing changed: no image reloads
          setSky(s => ({ ...s, frames, status: d.status, newest: d.archive_newest_mjd }));
          if (d.status.state !== "searching" && d.status.state !== "downloading") break;
          await sleep(2500, ac.signal);
        }
        if (!frames.length) return;
        setSky(s => ({ ...s, moversLoading: true }));
        const movers = await getMovers(spot, ac.signal);
        setSky(s => ({ ...s, movers, moversLoading: false }));
      } catch (e) {
        if (ac.signal.aborted) return;
        const msg = e instanceof TypeError ? "Cannot reach the server. Check your connection and try again." : (e as Error).message;
        setSky(s => ({ ...s, error: msg, moversLoading: false }));
      }
    })();
    return () => ac.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return sky;
}

const images = new Map<string, HTMLImageElement>();
const pending = new Map<string, Promise<void>>();
function load(url: string) {
  let p = pending.get(url);
  if (!p) {
    p = new Promise<void>(res => {
      const im = new Image();
      im.decoding = "async";
      im.onload = () => { images.set(url, im); res(); };
      im.onerror = () => { pending.delete(url); res(); };   // allow a retry on the next render
      im.src = url;
    });
    pending.set(url, p);
  }
  return p;
}

/** Loaded images for these URLs (null while loading). All load in parallel; re-renders as each one arrives. */
export function useImages(urls: string[]) {
  const [, bump] = useReducer((x: number) => x + 1, 0);
  const key = urls.join("|");
  useEffect(() => {
    let live = true;
    urls.forEach(u => { if (!images.has(u)) load(u).then(() => live && bump()); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return urls.map(u => images.get(u) ?? null);
}

export const reduceMotion = typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;
