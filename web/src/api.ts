export type Detector = "D1" | "D2" | "D3" | "D4" | "D5" | "D6";
export type Mode = "sky" | "diff" | "deep";

export interface Target { id: string; name: string; ra: number; dec: number; detector: Detector; pmra: number; pmdec: number }
export interface Frame { date: string; mjd: number; detector: Detector; file: string; folder: string; png_url: string }
export interface FetchStatus {
  state: "searching" | "downloading" | "done" | "error";
  total: number | null; error: string | null; available?: number; first_mjd?: number; last_mjd?: number;
}
export interface FramesResponse { frames: Frame[]; status: FetchStatus; archive_newest_mjd: number | null }
export interface MoverPoint {
  frame: number; px: number; py: number; ra: number; dec: number;
  flux: number | null; detected: boolean; wavelength_um: number | null;
}
export interface Mover {
  rate_arcsec_per_year: number; rate_err_arcsec_per_year: number; pa_deg: number; displacement_arcsec: number;
  span_days: number; fit_rms_arcsec: number; significance: number; n_detections: number; points: MoverPoint[];
}
export interface MoversResponse { movers: Mover[]; scale?: number; note?: string }
export interface Resolved { name: string; ra: number; dec: number; pm_mas_yr: number; pmra: number; pmdec: number }

export interface Spot { ra: number; dec: number; fov: string; det: Detector }
export const spotQuery = (s: Spot) => `ra=${s.ra}&dec=${s.dec}&fov=${s.fov}&detector=${s.det}`;

async function json<T>(url: string, signal?: AbortSignal): Promise<T> {
  const r = await fetch(url, { signal });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail ? String(body.detail) : r.status === 422 ? "RA must be 0 to 360 and Dec -90 to 90." : "The server had a problem. Try again.");
  return body as T;
}

export const getTargets = () => json<Target[]>("/api/targets");
export const getFrames = (s: Spot, signal: AbortSignal) => json<FramesResponse>(`/api/frames?${spotQuery(s)}`, signal);
export const getMovers = (s: Spot, signal: AbortSignal) => json<MoversResponse>(`/api/movers?${spotQuery(s)}`, signal);
export const resolveName = (name: string) => json<Resolved>(`/api/resolve?name=${encodeURIComponent(name)}`);

export const frameUrl = (f: Frame, mode: Mode, n: number) => (mode === "sky" ? f.png_url : `${f.png_url}&mode=${mode}&n=${n}`);
export const fitsUrl = (f: Frame) => `/api/frame.fits?folder=${encodeURIComponent(f.folder)}&file=${encodeURIComponent(f.file)}`;
