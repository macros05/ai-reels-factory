import React from "react";
import {
  AbsoluteFill,
  interpolate,
  random,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

// ============================================================================
// AdFX — shared "next-level" effect primitives for the four 40s ad versions.
// These augment primitives.tsx with: parallax-K, HUD overlays, lens streaks,
// horizontal letterbox, beat-sync helpers, chapter cards, device frames.
// ============================================================================

// ---------- BG ----------

export const NightBg: React.FC<{ children?: React.ReactNode }> = ({
  children,
}) => (
  <AbsoluteFill
    style={{
      background:
        "radial-gradient(120% 80% at 50% 50%, #0a0b0d 0%, #000 75%)",
      color: "#fff",
      fontFamily: "Helvetica, Arial, sans-serif",
    }}
  >
    {children}
  </AbsoluteFill>
);

// Cinematic horizontal letterbox for 1920×1080 → 2.39:1 inner active frame
export const HLetterbox: React.FC<{ size?: number }> = ({ size = 90 }) => (
  <>
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        height: size,
        background: "#000",
        zIndex: 70,
      }}
    />
    <div
      style={{
        position: "absolute",
        bottom: 0,
        left: 0,
        right: 0,
        height: size,
        background: "#000",
        zIndex: 70,
      }}
    />
  </>
);

// ---------- GRADES ----------

export const TealOrange: React.FC<{ strength?: number }> = ({
  strength = 1,
}) => (
  <AbsoluteFill
    style={{
      background:
        "linear-gradient(135deg, rgba(20,55,80,0.30) 0%, rgba(255,140,60,0.16) 100%)",
      mixBlendMode: "screen",
      opacity: strength,
      pointerEvents: "none",
    }}
  />
);

export const BleachBypass: React.FC = () => (
  <AbsoluteFill
    style={{
      background: "rgba(220,220,210,0.10)",
      mixBlendMode: "overlay",
      pointerEvents: "none",
    }}
  />
);

export const Vignette: React.FC<{ strength?: number }> = ({
  strength = 0.85,
}) => (
  <AbsoluteFill
    style={{
      background: `radial-gradient(120% 100% at 50% 50%, transparent 30%, rgba(0,0,0,${strength}) 100%)`,
      pointerEvents: "none",
    }}
  />
);

export const LensFlare: React.FC<{
  x?: number;
  y?: number;
  size?: number;
  opacity?: number;
  hue?: string;
}> = ({ x = 80, y = 25, size = 800, opacity = 0.35, hue = "255,180,120" }) => (
  <div
    style={{
      position: "absolute",
      left: `${x}%`,
      top: `${y}%`,
      width: size,
      height: size,
      transform: "translate(-50%, -50%)",
      background: `radial-gradient(closest-side, rgba(${hue},0.55), rgba(${hue},0.22) 30%, transparent 70%)`,
      filter: "blur(18px)",
      mixBlendMode: "screen",
      opacity,
      pointerEvents: "none",
    }}
  />
);

// Horizontal anamorphic-style lens streak
export const LensStreak: React.FC<{
  y?: number;
  opacity?: number;
  width?: string;
  hue?: string;
}> = ({ y = 50, opacity = 0.4, width = "60%", hue = "127,209,196" }) => (
  <div
    style={{
      position: "absolute",
      top: `${y}%`,
      left: 0,
      right: 0,
      height: 3,
      transform: "translateY(-50%)",
      background: `linear-gradient(90deg, transparent 20%, rgba(${hue},0.6) 50%, transparent 80%)`,
      width,
      margin: "0 auto",
      filter: "blur(2px)",
      mixBlendMode: "screen",
      opacity,
      pointerEvents: "none",
    }}
  />
);

// ---------- WATERMARK ----------

export const WatermarkH: React.FC<{
  top?: number;
  right?: number;
  dark?: boolean;
}> = ({ top = 120, right = 80, dark }) => {
  const color = dark ? "#000" : "#fff";
  return (
    <div
      style={{
        position: "absolute",
        top,
        right,
        display: "flex",
        alignItems: "center",
        gap: 10,
        opacity: 0.8,
        zIndex: 100,
        color,
      }}
    >
      <svg
        width={32}
        height={32}
        viewBox="0 0 24 24"
        fill="none"
        stroke={color}
        strokeWidth={1.6}
      >
        <rect x={3} y={3} width={18} height={18} rx={5} />
        <circle cx={12} cy={12} r={4} />
        <circle cx={17.5} cy={6.5} r={1} fill={color} />
      </svg>
      <div style={{ fontSize: 18, fontWeight: 600, letterSpacing: 1 }}>
        @BRAND
      </div>
    </div>
  );
};

// ---------- PARALLAX K ----------

export const ParallaxK: React.FC<{
  opacity?: number;
  size?: number;
  speed?: number;
  hue?: string;
}> = ({ opacity = 0.06, size = 1700, speed = 0.6, hue = "#ffffff" }) => {
  const frame = useCurrentFrame();
  const dx = interpolate(frame, [0, 600], [-60 * speed, 60 * speed]);
  const dy = interpolate(frame, [0, 600], [-20 * speed, 20 * speed]);
  return (
    <AbsoluteFill
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        pointerEvents: "none",
      }}
    >
      <span
        style={{
          fontSize: size,
          fontFamily: "Helvetica, Arial, sans-serif",
          fontWeight: 900,
          color: hue,
          opacity,
          letterSpacing: -size * 0.05,
          lineHeight: 0.8,
          transform: `translate(${dx}px, ${dy}px)`,
          textShadow: "0 0 100px rgba(255,255,255,0.08)",
        }}
      >
        K
      </span>
    </AbsoluteFill>
  );
};

// ---------- HUD ----------

export const HudCorners: React.FC<{
  color?: string;
  size?: number;
  inset?: number;
  thickness?: number;
  opacity?: number;
}> = ({
  color = "#7fd1c4",
  size = 90,
  inset = 80,
  thickness = 3,
  opacity = 0.9,
}) => {
  const sty = {
    position: "absolute" as const,
    width: size,
    height: size,
    borderColor: color,
    opacity,
  };
  return (
    <>
      <div
        style={{
          ...sty,
          top: inset,
          left: inset,
          borderTop: `${thickness}px solid`,
          borderLeft: `${thickness}px solid`,
        }}
      />
      <div
        style={{
          ...sty,
          top: inset,
          right: inset,
          borderTop: `${thickness}px solid`,
          borderRight: `${thickness}px solid`,
        }}
      />
      <div
        style={{
          ...sty,
          bottom: inset,
          left: inset,
          borderBottom: `${thickness}px solid`,
          borderLeft: `${thickness}px solid`,
        }}
      />
      <div
        style={{
          ...sty,
          bottom: inset,
          right: inset,
          borderBottom: `${thickness}px solid`,
          borderRight: `${thickness}px solid`,
        }}
      />
    </>
  );
};

export const ScanlinesSoft: React.FC<{ opacity?: number }> = ({
  opacity = 0.18,
}) => (
  <AbsoluteFill
    style={{
      backgroundImage:
        "repeating-linear-gradient(0deg, rgba(0,0,0,0.45) 0px, rgba(0,0,0,0.45) 1px, transparent 2px, transparent 4px)",
      mixBlendMode: "multiply",
      opacity,
      pointerEvents: "none",
    }}
  />
);

export const HudDataLine: React.FC<{
  label: string;
  value: string;
  color?: string;
  style?: React.CSSProperties;
}> = ({ label, value, color = "#7fd1c4", style }) => (
  <div
    style={{
      display: "flex",
      alignItems: "center",
      gap: 12,
      fontFamily: "JetBrains Mono, Courier, monospace",
      fontSize: 18,
      letterSpacing: 1.5,
      color,
      ...style,
    }}
  >
    <span style={{ opacity: 0.6 }}>{label}</span>
    <span style={{ fontWeight: 700 }}>{value}</span>
  </div>
);

export const HudCrosshair: React.FC<{
  x?: number;
  y?: number;
  size?: number;
  color?: string;
}> = ({ x = 50, y = 50, size = 120, color = "#7fd1c4" }) => (
  <div
    style={{
      position: "absolute",
      left: `${x}%`,
      top: `${y}%`,
      width: size,
      height: size,
      transform: "translate(-50%,-50%)",
      pointerEvents: "none",
      opacity: 0.85,
    }}
  >
    <div
      style={{
        position: "absolute",
        top: "50%",
        left: 0,
        right: 0,
        height: 1,
        background: color,
      }}
    />
    <div
      style={{
        position: "absolute",
        left: "50%",
        top: 0,
        bottom: 0,
        width: 1,
        background: color,
      }}
    />
    <div
      style={{
        position: "absolute",
        inset: "30%",
        border: `1px solid ${color}`,
        borderRadius: 4,
      }}
    />
  </div>
);

// Progress bar (used in pills + HUDs)
export const ProgressBar: React.FC<{
  progress: number;
  width: number;
  color?: string;
  height?: number;
}> = ({ progress, width, color = "#7fd1c4", height = 6 }) => (
  <div
    style={{
      width,
      height,
      background: "rgba(255,255,255,0.12)",
      borderRadius: height,
      overflow: "hidden",
    }}
  >
    <div
      style={{
        width: `${Math.max(0, Math.min(100, progress))}%`,
        height: "100%",
        background: `linear-gradient(90deg, ${color}, ${color}cc)`,
        boxShadow: `0 0 14px ${color}aa`,
        transition: "none",
      }}
    />
  </div>
);

// ---------- KINETIC ----------

// Three-direction word slam (used in V2)
export const SlamWord: React.FC<{
  word: string;
  fontSize: number;
  delay?: number;
  color?: string;
  fromX?: number;
}> = ({ word, fontSize, delay = 0, color = "#fff", fromX = 0 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const local = frame - delay;
  if (local < 0) return null;
  const s = spring({
    frame: local,
    fps,
    config: { damping: 7, mass: 0.6, stiffness: 240 },
  });
  const x = (1 - s) * fromX;
  const scale = 0.4 + s * 0.6;
  const op = Math.min(1, local / 4);
  return (
    <div
      style={{
        fontSize,
        fontWeight: 900,
        letterSpacing: -fontSize * 0.03,
        lineHeight: 0.92,
        transform: `translateX(${x}px) scale(${scale})`,
        opacity: op,
        color,
        textShadow: `0 0 ${fontSize * 0.15}px rgba(255,255,255,0.25)`,
      }}
    >
      {word}
    </div>
  );
};

// Beat-sync scale pulse helper. Returns 1.0 + amplitude on every period frames.
export const useBeatPulse = (
  startFrame: number,
  periodFrames: number,
  amplitude = 0.04
): number => {
  const frame = useCurrentFrame();
  const local = frame - startFrame;
  if (local < 0) return 1;
  const phase = (local % periodFrames) / periodFrames;
  // Quick attack, slow release on each beat
  const env = Math.max(0, 1 - phase * 1.2);
  return 1 + env * env * amplitude;
};

// ---------- CHAPTER CARD ----------

export const ChapterCard: React.FC<{
  num?: string;
  kicker?: string;
  title: string;
  align?: "start" | "center" | "end";
  opacity?: number;
}> = ({ num, kicker, title, align = "start", opacity = 1 }) => (
  <div
    style={{
      display: "flex",
      flexDirection: "column",
      gap: 12,
      alignItems:
        align === "center"
          ? "center"
          : align === "end"
          ? "flex-end"
          : "flex-start",
      textAlign:
        align === "center" ? "center" : align === "end" ? "right" : "left",
      opacity,
    }}
  >
    {num && (
      <div
        style={{
          fontSize: 22,
          opacity: 0.55,
          letterSpacing: 6,
          fontFamily: "JetBrains Mono, Courier, monospace",
          fontWeight: 500,
        }}
      >
        {num}
      </div>
    )}
    {kicker && (
      <div
        style={{
          fontSize: 22,
          opacity: 0.6,
          letterSpacing: 8,
          fontWeight: 500,
        }}
      >
        {kicker}
      </div>
    )}
    <div
      style={{
        fontSize: 110,
        fontWeight: 200,
        letterSpacing: -2,
        lineHeight: 0.95,
        whiteSpace: "pre-line",
      }}
    >
      {title}
    </div>
  </div>
);

// ---------- DEVICE FRAME (V4) ----------

export const DeviceFrame: React.FC<{
  children: React.ReactNode;
  color?: string;
  thickness?: number;
}> = ({ children, color = "#7fd1c4", thickness = 2 }) => (
  <div
    style={{
      position: "relative",
      border: `${thickness}px solid ${color}`,
      padding: 4,
      borderRadius: 18,
      boxShadow: `0 0 28px ${color}66`,
    }}
  >
    <div
      style={{
        position: "absolute",
        top: -1,
        left: 30,
        right: 30,
        height: 2,
        background: color,
      }}
    />
    {children}
  </div>
);

// ---------- BEAT FLASH ----------

export const BeatFlash: React.FC<{ on: boolean; color?: string }> = ({
  on,
  color = "#fff",
}) => {
  if (!on) return null;
  return (
    <AbsoluteFill
      style={{
        background: color,
        opacity: 0.5,
        pointerEvents: "none",
        zIndex: 60,
      }}
    />
  );
};

// Strong shake on impact frames
export const useImpactShake = (
  beatFrames: number[],
  durFrames = 6,
  mag = 14
): { x: number; y: number } => {
  const frame = useCurrentFrame();
  for (const b of beatFrames) {
    const local = frame - b;
    if (local >= 0 && local < durFrames) {
      const decay = 1 - local / durFrames;
      return {
        x: (random(`sx-${frame}`) - 0.5) * 2 * mag * decay,
        y: (random(`sy-${frame}`) - 0.5) * 2 * mag * decay,
      };
    }
  }
  return { x: 0, y: 0 };
};
