import type { Detector, Mover, Target } from "./api";

export const PIX = 6.15; // arcsec per SPHEREx pixel

export const DETECTORS: { id: Detector; band: string; mid: string; color: string }[] = [
  { id: "D1", band: "0.75-1.09", mid: "0.9", color: "#E3A43A" },
  { id: "D2", band: "1.10-1.62", mid: "1.4", color: "#DD7A3C" },
  { id: "D3", band: "1.63-2.41", mid: "2.0", color: "#C9476A" },
  { id: "D4", band: "2.42-3.82", mid: "3.1", color: "#9A3FB0" },
  { id: "D5", band: "3.83-4.41", mid: "4.1", color: "#6C4FD0" },
  { id: "D6", band: "4.42-5.00", mid: "4.7", color: "#3D5BD6" },
];

export const FOVS = [
  { v: "0.05", label: "Close up", title: "3 arcminutes across" },
  { v: "0.1", label: "Medium", title: "6 arcminutes across, a tenth of the full Moon's width" },
  { v: "0.2", label: "Wide", title: "12 arcminutes across" },
];

export const KIND: Record<string, [string, "bd" | "st" | "var"]> = {
  wise0855: ["Brown dwarf", "bd"], eps_indi_b: ["Brown dwarf", "bd"], luhman16: ["Brown dwarf", "bd"],
  barnards_star: ["Fast star", "st"], kapteyn: ["Fast star", "st"], groombridge: ["Fast star", "st"], wolf359: ["Fast star", "st"],
  rw_aur: ["Variable", "var"], r_dra: ["Variable", "var"],
};

export const DESCRIBE: Record<string, string> = {
  wise0855: "Coldest known brown dwarf, 7.4 light years away",
  barnards_star: "The fastest-moving star in our sky",
  eps_indi_b: "A pair of brown dwarfs near a bright star",
  rw_aur: "A young star that flickers in brightness",
  r_dra: "A giant star that slowly brightens and fades",
  kapteyn: "One of the oldest stars near the Sun, racing past us",
  groombridge: "A fast star crossing the sky in Ursa Major",
  wolf359: "A small red dwarf 7.9 light years away",
  luhman16: "The closest pair of brown dwarfs, 6.5 light years away",
};

export const fmtDate = (iso: string) =>
  new Date(iso.endsWith("Z") ? iso : iso + "Z").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
export const mjdDate = (mjd: number) => fmtDate(new Date((mjd - 40587) * 864e5).toISOString().slice(0, 19));

export const compass = (pa: number) =>
  ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"][Math.round(pa / 45) % 8];

/** The speed in everyday terms: a 2.4 cm coin seen from this many km slides its own width in a year. */
export function coinKm(rateArcsecPerYear: number) {
  const km = 0.024 / (rateArcsecPerYear / 206265) / 1000;
  return km < 10 ? km.toFixed(1) : km.toFixed(0);
}

export const confidence = (sigma: number) => (sigma >= 10 ? "Very high" : sigma >= 5 ? "High" : "Low");

export interface Catalog { pmra: number; pmdec: number }

/** Compare a mover with the catalog proper motion, when the mover is the named target (within 40"). */
export function catalogMatch(m: Mover, catalog: Catalog | null, ra: number, dec: number) {
  if (!catalog) return null;
  const p = m.points[Math.floor(m.points.length / 2)];
  const off = Math.hypot((p.ra - ra) * Math.cos((dec * Math.PI) / 180), p.dec - dec) * 3600;
  const rate = Math.hypot(catalog.pmra, catalog.pmdec) / 1000;
  if (off > 40 || rate < 0.2) return null;
  const pa = ((Math.atan2(catalog.pmra, catalog.pmdec) * 180) / Math.PI + 360) % 360;
  const dRate = (Math.abs(m.rate_arcsec_per_year - rate) / rate) * 100;
  const dPa = Math.abs(((m.pa_deg - pa + 540) % 360) - 180);
  return { rate, pa, dRate, dPa, good: dRate < 25 && dPa < 20 };
}

/** A random spot, uniform on the sphere, at least 20 deg from the crowded Milky Way plane. */
export function randomSpot() {
  for (;;) {
    const ra = Math.random() * 360, dec = (Math.asin(2 * Math.random() - 1) * 180) / Math.PI;
    const r = (ra * Math.PI) / 180, d = (dec * Math.PI) / 180; // galactic latitude from the J2000 north galactic pole
    const b = (Math.asin(Math.sin(d) * Math.sin(0.4734773) + Math.cos(d) * Math.cos(0.4734773) * Math.cos(r - 3.3660329)) * 180) / Math.PI;
    if (Math.abs(b) >= 20) return { ra: +ra.toFixed(4), dec: +dec.toFixed(4) };
  }
}

export function downloadCsv(movers: Mover[], dates: string[], name: string) {
  const rows: (string | number | boolean)[][] = [["object", "frame", "date_utc", "ra_deg", "dec_deg", "detected", "flux", "wavelength_um", "rate_arcsec_per_year", "pa_deg"]];
  movers.forEach((m, k) => m.points.forEach((p, i) =>
    rows.push([k + 1, i + 1, dates[i] ?? "", p.ra, p.dec, p.detected, p.flux ?? "", p.wavelength_um ?? "", m.rate_arcsec_per_year, m.pa_deg])));
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([rows.map(r => r.join(",")).join("\n")], { type: "text/csv" }));
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

export const isTargetHere = (t: Target, ra: number, dec: number) => Math.abs(t.ra - ra) < 1e-3 && Math.abs(t.dec - dec) < 1e-3;
