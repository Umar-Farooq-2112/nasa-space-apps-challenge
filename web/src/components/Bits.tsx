import type { ReactNode } from "react";

/** Charon, drawn: grey ice with the red-brown north pole (Mordor Macula) and the Serenity Chasma belt. */
export function Logo({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" className="logo">
      <defs>
        <radialGradient id="chg" cx=".36" cy=".34" r=".78">
          <stop offset="0" stopColor="#E4E1DC" /><stop offset=".55" stopColor="#9B968F" /><stop offset="1" stopColor="#34322F" />
        </radialGradient>
        <clipPath id="chc"><circle cx="16" cy="16" r="13" /></clipPath>
      </defs>
      <circle cx="16" cy="16" r="13" fill="url(#chg)" />
      <g clipPath="url(#chc)">
        <ellipse cx="14.5" cy="4" rx="10.5" ry="6.2" fill="#7B3F27" opacity=".9" />
        <ellipse cx="14" cy="5.5" rx="7" ry="3.2" fill="#5A2C1C" opacity=".6" />
        <path d="M2 16.5c6 2.2 14 2.6 28-1.5" stroke="#55514C" strokeWidth="1.3" fill="none" opacity=".7" />
        <path d="M3 19c7 1.6 15 1.4 26-2.2" stroke="#C9C5BF" strokeWidth=".5" fill="none" opacity=".5" />
        <circle cx="21" cy="22" r="1.6" fill="#6E6A65" opacity=".7" />
        <circle cx="11" cy="24" r="1.1" fill="#6E6A65" opacity=".6" />
        <circle cx="24.5" cy="12.5" r=".9" fill="#6E6A65" opacity=".6" />
        <path d="M16 3a13 13 0 0 1 0 26a13 13 0 0 0 0-26z" fill="#000" opacity=".28" transform="translate(5 0)" />
      </g>
    </svg>
  );
}

export interface SegOption<T extends string> { v: T; label: ReactNode; title?: string }

export function Segmented<T extends string>({ options, value, onChange, label, className = "" }:
  { options: SegOption<T>[]; value: T; onChange: (v: T) => void; label: string; className?: string }) {
  return (
    <div className={`seg ${className}`} role="radiogroup" aria-label={label}>
      {options.map(o => (
        <button key={o.v} type="button" role="radio" aria-checked={o.v === value} title={o.title} onClick={() => onChange(o.v)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Spinner({ small = false }: { small?: boolean }) {
  return <span className={small ? "spinner small" : "spinner"} aria-hidden="true" />;
}

export function Section({ title, aside, children }: { title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="section">
      <div className="section-head"><h2>{title}</h2>{aside}</div>
      {children}
    </section>
  );
}
