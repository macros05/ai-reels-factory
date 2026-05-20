import React from "react";
import {
  AbsoluteFill,
  interpolate,
  random,
  useCurrentFrame,
} from "remotion";

/* ----------------------------------------------------------------------- */
/* Backgrounds                                                              */
/* ----------------------------------------------------------------------- */

export const BlackBg: React.FC<{ children?: React.ReactNode }> = ({ children }) => (
  <AbsoluteFill style={{ background: "radial-gradient(120% 80% at 50% 50%, #0a0a0a 0%, #000 75%)", color: "#fff", fontFamily: "Helvetica, Arial, sans-serif" }}>
    {children}
  </AbsoluteFill>
);

export const WhiteBg: React.FC<{ children?: React.ReactNode }> = ({ children }) => (
  <AbsoluteFill style={{ background: "#fff", color: "#000", fontFamily: "Helvetica, Arial, sans-serif" }}>
    {children}
  </AbsoluteFill>
);

/* ----------------------------------------------------------------------- */
/* @BRAND watermark                                                      */
/* ----------------------------------------------------------------------- */

export const Watermark: React.FC<{ dark?: boolean; bottom?: boolean }> = ({ dark, bottom }) => {
  const color = dark ? "#000" : "#fff";
  return (
    <div
      style={{
        position: "absolute",
        top: bottom ? undefined : 70,
        bottom: bottom ? 70 : undefined,
        right: 56,
        display: "flex",
        flexDirection: "column",
        alignItems: "flex-end",
        gap: 4,
        opacity: 0.85,
        letterSpacing: 0.5,
        zIndex: 100,
        color,
      }}
    >
      <svg width={40} height={40} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.6}>
        <rect x={3} y={3} width={18} height={18} rx={5} />
        <circle cx={12} cy={12} r={4} />
        <circle cx={17.5} cy={6.5} r={1} fill={color} />
      </svg>
      <div style={{ fontSize: 20, fontWeight: 600 }}>@BRAND</div>
    </div>
  );
};

/* ----------------------------------------------------------------------- */
/* Film grain                                                               */
/* ----------------------------------------------------------------------- */

export const Grain: React.FC<{ intensity?: number }> = ({ intensity = 0.05 }) => {
  const frame = useCurrentFrame();
  const seed = Math.floor(frame / 2);
  return (
    <AbsoluteFill
      style={{
        backgroundImage: `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='320' height='320'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='1.4' numOctaves='2' seed='${seed}'/><feColorMatrix values='0 0 0 0 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0.6 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>")`,
        backgroundSize: "320px 320px",
        opacity: intensity,
        mixBlendMode: "overlay",
        pointerEvents: "none",
      }}
    />
  );
};

/* ----------------------------------------------------------------------- */
/* CRT scanlines                                                            */
/* ----------------------------------------------------------------------- */

export const Scanlines: React.FC<{ opacity?: number }> = ({ opacity = 0.25 }) => (
  <AbsoluteFill
    style={{
      backgroundImage:
        "repeating-linear-gradient(0deg, rgba(0,0,0,0.4) 0px, rgba(0,0,0,0.4) 1px, transparent 2px, transparent 4px)",
      mixBlendMode: "multiply",
      opacity,
      pointerEvents: "none",
    }}
  />
);

/* ----------------------------------------------------------------------- */
/* Flash white intro                                                        */
/* ----------------------------------------------------------------------- */

export const FlashIn: React.FC<{ frames?: number }> = ({ frames = 4 }) => {
  const frame = useCurrentFrame();
  const o = interpolate(frame, [0, frames], [1, 0], { extrapolateRight: "clamp" });
  if (o <= 0) return null;
  return <AbsoluteFill style={{ backgroundColor: "#fff", opacity: o, zIndex: 50 }} />;
};

/* ----------------------------------------------------------------------- */
/* Chromatic aberration                                                     */
/* ----------------------------------------------------------------------- */

export const Chroma: React.FC<{ children: React.ReactNode; offset?: number; style?: React.CSSProperties }> = ({ children, offset = 6, style }) => (
  <div style={{ position: "relative", ...style }}>
    <div style={{ position: "absolute", inset: 0, color: "#ff2244", transform: `translate(-${offset}px, ${offset / 2}px)`, mixBlendMode: "screen" }}>{children}</div>
    <div style={{ position: "absolute", inset: 0, color: "#22ddff", transform: `translate(${offset}px, -${offset / 2}px)`, mixBlendMode: "screen" }}>{children}</div>
    <div style={{ position: "relative", color: "#fff" }}>{children}</div>
  </div>
);

/* ----------------------------------------------------------------------- */
/* Shake helper                                                             */
/* ----------------------------------------------------------------------- */

export const useShake = (start: number, durFrames: number, magnitude = 12) => {
  const frame = useCurrentFrame();
  const local = frame - start;
  if (local < 0 || local > durFrames) return { x: 0, y: 0 };
  const decay = Math.max(0, 1 - local / durFrames);
  const x = (random(`sx-${frame}`) - 0.5) * 2 * magnitude * decay;
  const y = (random(`sy-${frame}`) - 0.5) * 2 * magnitude * decay;
  return { x, y };
};

/* ----------------------------------------------------------------------- */
/* Glitch scanbands                                                         */
/* ----------------------------------------------------------------------- */

export const Glitch: React.FC<{ active: boolean; intensity?: number }> = ({ active, intensity = 1 }) => {
  const frame = useCurrentFrame();
  if (!active) return null;
  const bands = 14;
  return (
    <AbsoluteFill style={{ pointerEvents: "none", mixBlendMode: "screen", zIndex: 80 }}>
      {Array.from({ length: bands }).map((_, i) => {
        const y = (i / bands) * 100;
        const h = 100 / bands;
        const shift = (random(`g-${frame}-${i}`) - 0.5) * 40 * intensity;
        const o = random(`go-${frame}-${i}`) > 0.55 ? 0.7 * intensity : 0;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              top: `${y}%`,
              left: 0,
              width: "100%",
              height: `${h}%`,
              background: i % 2 === 0 ? "rgba(255,60,60,0.5)" : "rgba(60,255,255,0.5)",
              transform: `translateX(${shift}px)`,
              opacity: o,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};

/* ----------------------------------------------------------------------- */
/* Counter                                                                  */
/* ----------------------------------------------------------------------- */

export const Counter: React.FC<{ target: number; durationFrames: number; style?: React.CSSProperties; suffix?: string }> = ({ target, durationFrames, style, suffix = "" }) => {
  const frame = useCurrentFrame();
  const t = Math.min(1, frame / durationFrames);
  const eased = 1 - Math.pow(1 - t, 3);
  const value = Math.round(target * eased);
  return <span style={style}>{value.toLocaleString("es-ES")}{suffix}</span>;
};

/* ----------------------------------------------------------------------- */
/* Cinematic letterbox bars                                                */
/* ----------------------------------------------------------------------- */

export const Letterbox: React.FC<{ size?: number }> = ({ size = 220 }) => (
  <>
    <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: size, background: "#000", zIndex: 70 }} />
    <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: size, background: "#000", zIndex: 70 }} />
  </>
);

/* ----------------------------------------------------------------------- */
/* HUD corner markers (TL/TR/BL/BR brackets)                                */
/* ----------------------------------------------------------------------- */

export const HudCorners: React.FC<{ color?: string; size?: number; inset?: number }> = ({ color = "#7fd1c4", size = 80, inset = 50 }) => {
  const sty = { position: "absolute" as const, width: size, height: size, borderColor: color, opacity: 0.85 };
  const t = 4;
  return (
    <>
      <div style={{ ...sty, top: inset, left: inset, borderTop: `${t}px solid`, borderLeft: `${t}px solid` }} />
      <div style={{ ...sty, top: inset, right: inset, borderTop: `${t}px solid`, borderRight: `${t}px solid` }} />
      <div style={{ ...sty, bottom: inset, left: inset, borderBottom: `${t}px solid`, borderLeft: `${t}px solid` }} />
      <div style={{ ...sty, bottom: inset, right: inset, borderBottom: `${t}px solid`, borderRight: `${t}px solid` }} />
    </>
  );
};
