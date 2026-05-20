import React from "react";
import {
  AbsoluteFill,
  OffthreadVideo,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

// ============================================================================
// MinimalCommon — extremely simple, recurring building blocks for the 4 ads.
// Aesthetic rule: ONE clip per scene + ONE caption max + letterbox + watermark
// + grain. No glitch, no chromatic, no kinetic montages. All the heavy lifting
// happens in the dedicated LogoSpectacle scenes.
// ============================================================================

export const NightBg: React.FC<{ children?: React.ReactNode }> = ({
  children,
}) => (
  <AbsoluteFill
    style={{
      background: "radial-gradient(120% 80% at 50% 50%, #0a0a0a 0%, #000 75%)",
      color: "#fff",
      fontFamily: "Helvetica, Arial, sans-serif",
    }}
  >
    {children}
  </AbsoluteFill>
);

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

export const Vignette: React.FC<{ strength?: number }> = ({
  strength = 0.7,
}) => (
  <AbsoluteFill
    style={{
      background: `radial-gradient(120% 100% at 50% 50%, transparent 30%, rgba(0,0,0,${strength}) 100%)`,
      pointerEvents: "none",
    }}
  />
);

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

export const WatermarkH: React.FC<{ dark?: boolean }> = ({ dark }) => {
  const color = dark ? "#000" : "#fff";
  return (
    <div
      style={{
        position: "absolute",
        top: 120,
        right: 80,
        display: "flex",
        alignItems: "center",
        gap: 10,
        opacity: 0.75,
        zIndex: 100,
        color,
      }}
    >
      <svg
        width={30}
        height={30}
        viewBox="0 0 24 24"
        fill="none"
        stroke={color}
        strokeWidth={1.6}
      >
        <rect x={3} y={3} width={18} height={18} rx={5} />
        <circle cx={12} cy={12} r={4} />
        <circle cx={17.5} cy={6.5} r={1} fill={color} />
      </svg>
      <div style={{ fontSize: 16, fontWeight: 600, letterSpacing: 1 }}>
        @BRAND
      </div>
    </div>
  );
};

export const FlashIn: React.FC<{ frames?: number }> = ({ frames = 4 }) => {
  const frame = useCurrentFrame();
  const o = interpolate(frame, [0, frames], [1, 0], {
    extrapolateRight: "clamp",
  });
  if (o <= 0) return null;
  return (
    <AbsoluteFill
      style={{ backgroundColor: "#fff", opacity: o, zIndex: 80 }}
    />
  );
};

// Default cinematic filter
const FILTER = "brightness(0.85) contrast(1.16) saturate(0.95)";

// ============================================================================
// Scene primitives — one clip, optional caption, slow push-in
// ============================================================================

/** A clip-scene with the most common minimal treatment. */
export const ClipScene: React.FC<{
  src: string;
  startFrom?: number;
  filter?: string;
  zoomStart?: number;
  zoomEnd?: number;
  fadeOutAtEnd?: boolean;
  children?: React.ReactNode;
}> = ({
  src,
  startFrom = 0,
  filter = FILTER,
  zoomStart = 1.02,
  zoomEnd = 1.08,
  fadeOutAtEnd = false,
  children,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const zoom = interpolate(frame, [0, durationInFrames], [zoomStart, zoomEnd]);
  const sceneOp = fadeOutAtEnd
    ? interpolate(
        frame,
        [0, 8, durationInFrames - 10, durationInFrames],
        [0, 1, 1, 0]
      )
    : interpolate(frame, [0, 8], [0, 1], { extrapolateRight: "clamp" });
  return (
    <NightBg>
      <AbsoluteFill style={{ transform: `scale(${zoom})`, filter, opacity: sceneOp }}>
        <OffthreadVideo
          src={staticFile(src)}
          muted
          startFrom={startFrom}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </AbsoluteFill>
      <Vignette strength={0.6} />
      <HLetterbox />
      <WatermarkH />
      {children}
      <Grain intensity={0.05} />
    </NightBg>
  );
};

/** A single bottom-left caption that fades in and out. */
export const Caption: React.FC<{
  kicker?: string;
  title: string;
  align?: "left" | "right" | "center";
  bottom?: number;
  appearAt?: number;
  disappearAt?: number | null;
  bold?: boolean;
}> = ({
  kicker,
  title,
  align = "left",
  bottom = 150,
  appearAt = 14,
  disappearAt = null,
  bold = false,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const out = disappearAt ?? durationInFrames - 10;
  const op = Math.min(
    interpolate(frame, [appearAt, appearAt + 20], [0, 1], {
      extrapolateRight: "clamp",
    }),
    interpolate(frame, [out, out + 18], [1, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    })
  );
  return (
    <div
      style={{
        position: "absolute",
        bottom,
        left: align === "left" ? 90 : align === "center" ? 0 : undefined,
        right: align === "right" ? 90 : align === "center" ? 0 : undefined,
        textAlign: align,
        opacity: op,
        zIndex: 50,
        ...(align === "center"
          ? { left: 0, right: 0, marginInline: "auto", width: "80%" }
          : {}),
      }}
    >
      {kicker && (
        <div
          style={{
            fontFamily: "JetBrains Mono, Courier, monospace",
            fontSize: 18,
            opacity: 0.55,
            letterSpacing: 8,
            marginBottom: 12,
            fontWeight: 500,
          }}
        >
          {kicker}
        </div>
      )}
      <div
        style={{
          fontSize: bold ? 96 : 72,
          fontWeight: bold ? 800 : 200,
          letterSpacing: -2,
          lineHeight: 0.95,
          textShadow: "0 4px 30px rgba(0,0,0,0.7)",
          whiteSpace: "pre-line",
        }}
      >
        {title}
      </div>
    </div>
  );
};

/** A pure text card on solid background — for tagline moments. */
export const TextCard: React.FC<{
  kicker?: string;
  title: string;
  sub?: string;
  align?: "left" | "center";
}> = ({ kicker, title, sub, align = "center" }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const op = Math.min(
    interpolate(frame, [0, 20], [0, 1], { extrapolateRight: "clamp" }),
    interpolate(
      frame,
      [durationInFrames - 14, durationInFrames],
      [1, 0],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    )
  );
  return (
    <NightBg>
      <FlashIn frames={5} />
      <HLetterbox />
      <WatermarkH />
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: align === "center" ? "center" : "flex-start",
          textAlign: align,
          padding: align === "center" ? "0" : "0 0 0 100px",
          opacity: op,
        }}
      >
        {kicker && (
          <div
            style={{
              fontFamily: "JetBrains Mono, Courier, monospace",
              fontSize: 22,
              opacity: 0.55,
              letterSpacing: 10,
              marginBottom: 22,
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
            letterSpacing: -3,
            lineHeight: 0.96,
            whiteSpace: "pre-line",
          }}
        >
          {title}
        </div>
        {sub && (
          <div
            style={{
              marginTop: 24,
              fontSize: 22,
              opacity: 0.6,
              letterSpacing: 8,
            }}
          >
            {sub}
          </div>
        )}
      </AbsoluteFill>
      <Vignette strength={0.5} />
      <Grain intensity={0.06} />
    </NightBg>
  );
};
