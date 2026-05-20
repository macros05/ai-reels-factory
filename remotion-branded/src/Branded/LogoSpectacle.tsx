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
// LogoSpectacle — four elaborate logo reveal sequences for the ad versions.
// Each is a self-contained AbsoluteFill that plays for its given durationFrames.
// Heavy on the logo, light on everything else. Designed for minimalist scenes
// to lead into a single, spectacular brand moment.
// ============================================================================

const TEAL = "#7fd1c4";
const WORD = "BRAND";

// Small in-svg K mark (circle + monogram)
const KMark: React.FC<{
  size: number;
  color?: string;
  innerColor?: string;
  strokeW?: number;
}> = ({ size, color = "#fff", innerColor = "#000", strokeW = 5 }) => (
  <svg width={size} height={size} viewBox="0 0 100 100" style={{ flexShrink: 0 }}>
    <circle cx={50} cy={50} r={47} fill={color} />
    <path
      d="M 30 30 L 70 30 L 70 70 L 30 70 Z M 30 30 L 70 70"
      stroke={innerColor}
      strokeWidth={strokeW}
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

// =================================================================
// 1) ARCHITECTURE — the K is drawn from architectural blueprint lines.
//    Grid → guides → K traces → ink-fill → wordmark wipes in.
// =================================================================
export const LogoArchitecture: React.FC<{ height?: number }> = ({
  height = 200,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // Phase timings
  const phaseGrid = interpolate(frame, [0, 12], [0, 1], {
    extrapolateRight: "clamp",
  });
  const phaseGuides = interpolate(frame, [10, 26], [0, 1], {
    extrapolateRight: "clamp",
  });
  const phaseK1 = interpolate(frame, [20, 38], [0, 1], {
    extrapolateRight: "clamp",
  });
  const phaseK2 = interpolate(frame, [30, 48], [0, 1], {
    extrapolateRight: "clamp",
  });
  const phaseK3 = interpolate(frame, [40, 58], [0, 1], {
    extrapolateRight: "clamp",
  });
  const phaseFill = interpolate(frame, [52, 72], [0, 1], {
    extrapolateRight: "clamp",
  });
  const phaseWord = interpolate(frame, [62, 96], [0, 1], {
    extrapolateRight: "clamp",
  });
  const phaseSettle = interpolate(frame, [88, 110], [0, 1], {
    extrapolateRight: "clamp",
  });

  // K geometry (within 100×100 viewBox, mirrors the K monogram)
  const Kv = { x1: 32, y1: 22, x2: 32, y2: 78 };
  const Ku = { x1: 32, y1: 50, x2: 64, y2: 22 };
  const Kl = { x1: 38, y1: 56, x2: 64, y2: 78 };

  const dashLen = (s: { x1: number; y1: number; x2: number; y2: number }) =>
    Math.hypot(s.x2 - s.x1, s.y2 - s.y1);

  const W = height * 4.6; // wordmark approximate width
  return (
    <div
      style={{
        position: "relative",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 14,
      }}
    >
      {/* Mark area, sized to height */}
      <div
        style={{
          position: "relative",
          width: height + 60,
          height: height + 60,
        }}
      >
        <svg
          viewBox="0 0 100 100"
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
        >
          {/* Bounding-box grid (faint) */}
          <g opacity={0.4 * phaseGrid}>
            {[20, 40, 60, 80].map((p) => (
              <React.Fragment key={p}>
                <line
                  x1={p}
                  y1={6}
                  x2={p}
                  y2={94}
                  stroke={TEAL}
                  strokeWidth={0.25}
                  strokeDasharray="1 1"
                />
                <line
                  x1={6}
                  y1={p}
                  x2={94}
                  y2={p}
                  stroke={TEAL}
                  strokeWidth={0.25}
                  strokeDasharray="1 1"
                />
              </React.Fragment>
            ))}
          </g>
          {/* Outer guide square */}
          <rect
            x={6}
            y={6}
            width={88}
            height={88}
            fill="none"
            stroke={TEAL}
            strokeWidth={0.4}
            strokeDasharray="2 1.5"
            opacity={0.85 * phaseGuides}
          />
          {/* Inner construction circle */}
          <circle
            cx={50}
            cy={50}
            r={47}
            fill="none"
            stroke={TEAL}
            strokeWidth={0.5}
            strokeDasharray={`${(2 * Math.PI * 47) * phaseGuides} 300`}
            opacity={0.9}
          />
          {/* K — vertical stem */}
          <line
            x1={Kv.x1}
            y1={Kv.y1}
            x2={Kv.x2}
            y2={Kv.y2}
            stroke="#fff"
            strokeWidth={3}
            strokeLinecap="round"
            strokeDasharray={dashLen(Kv)}
            strokeDashoffset={(1 - phaseK1) * dashLen(Kv)}
          />
          {/* K — upper diagonal */}
          <line
            x1={Ku.x1}
            y1={Ku.y1}
            x2={Ku.x2}
            y2={Ku.y2}
            stroke="#fff"
            strokeWidth={3}
            strokeLinecap="round"
            strokeDasharray={dashLen(Ku)}
            strokeDashoffset={(1 - phaseK2) * dashLen(Ku)}
          />
          {/* K — lower diagonal */}
          <line
            x1={Kl.x1}
            y1={Kl.y1}
            x2={Kl.x2}
            y2={Kl.y2}
            stroke="#fff"
            strokeWidth={3}
            strokeLinecap="round"
            strokeDasharray={dashLen(Kl)}
            strokeDashoffset={(1 - phaseK3) * dashLen(Kl)}
          />
          {/* Ink-fill circle that grows behind the K */}
          <circle
            cx={50}
            cy={50}
            r={47 * phaseFill}
            fill="#fff"
            opacity={phaseFill}
          />
          {/* K monogram on top of the white fill */}
          <path
            d="M 30 30 L 70 30 L 70 70 L 30 70 Z M 30 30 L 70 70"
            stroke="#000"
            strokeWidth={5}
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity={phaseFill}
          />
        </svg>
      </div>
      {/* Wordmark wipes in from left to right */}
      <div
        style={{
          fontFamily: "Helvetica, Arial, sans-serif",
          fontWeight: 900,
          fontSize: height,
          letterSpacing: -height * 0.06,
          lineHeight: 1,
          color: "#fff",
          clipPath: `inset(0 ${100 - phaseWord * 100}% 0 0)`,
          transform: `translateY(${(1 - phaseSettle) * 20}px)`,
        }}
      >
        {WORD}
      </div>
    </div>
  );
};

// =================================================================
// 2) PARTICLES — thousands of dots flow in from random positions
//    and assemble into the wordmark via spring per-letter settling.
// =================================================================
export const LogoParticles: React.FC<{ height?: number }> = ({
  height = 180,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const letters = WORD.split("");

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: height * 0.15,
      }}
    >
      <ParticleMark size={height} delay={0} />
      <div style={{ display: "flex", gap: 0 }}>
        {letters.map((L, i) => (
          <ParticleLetter key={i} char={L} fontSize={height} delay={6 + i * 4} />
        ))}
      </div>
    </div>
  );
};

const ParticleMark: React.FC<{ size: number; delay: number }> = ({
  size,
  delay,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const N = 80;
  const particles = Array.from({ length: N });
  return (
    <div style={{ position: "relative", width: size, height: size }}>
      {particles.map((_, i) => {
        const local = frame - delay - i * 0.3;
        const s = spring({
          frame: Math.max(0, local),
          fps,
          config: { damping: 13, mass: 0.8, stiffness: 90 },
        });
        // Target on circle perimeter
        const a = (i / N) * Math.PI * 2;
        const tx = Math.cos(a) * (size * 0.48) + size / 2;
        const ty = Math.sin(a) * (size * 0.48) + size / 2;
        // Start far away
        const ox = random(`px-${i}`) * size * 4 - size * 2;
        const oy = random(`py-${i}`) * size * 4 - size * 2;
        const x = ox + (tx - ox) * s;
        const y = oy + (ty - oy) * s;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: x - 2,
              top: y - 2,
              width: 4,
              height: 4,
              borderRadius: "50%",
              background: "#fff",
              opacity: s,
              boxShadow: "0 0 4px rgba(255,255,255,0.7)",
            }}
          />
        );
      })}
      {/* Final solid K mark fades in after particles arrive */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          opacity: interpolate(frame, [delay + 28, delay + 44], [0, 1], {
            extrapolateRight: "clamp",
          }),
        }}
      >
        <KMark size={size} color="#fff" innerColor="#000" />
      </div>
    </div>
  );
};

const ParticleLetter: React.FC<{
  char: string;
  fontSize: number;
  delay: number;
}> = ({ char, fontSize, delay }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const local = frame - delay;
  const s = spring({
    frame: Math.max(0, local),
    fps,
    config: { damping: 11, mass: 0.7, stiffness: 110 },
  });
  const y = (1 - s) * fontSize * 0.6;
  const blur = (1 - s) * 16;
  const op = interpolate(local, [-8, 0, 10], [0, 0.2, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <span
      style={{
        display: "inline-block",
        fontFamily: "Helvetica, Arial, sans-serif",
        fontWeight: 900,
        fontSize,
        letterSpacing: -fontSize * 0.06,
        lineHeight: 1,
        color: "#fff",
        transform: `translateY(${y}px)`,
        filter: `blur(${blur}px)`,
        opacity: op,
      }}
    >
      {char}
    </span>
  );
};

// =================================================================
// 3) ECLIPSE — a perfect black disc grows over a teal sun, eclipses
//    it leaving a corona ring. K rises from below behind the corona.
//    Wordmark fades up after the corona settles.
// =================================================================
export const LogoEclipse: React.FC<{ height?: number }> = ({
  height = 200,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const sunGrow = spring({
    frame,
    fps,
    config: { damping: 12, mass: 1.0, stiffness: 80 },
  });
  const eclipse = spring({
    frame: frame - 20,
    fps,
    config: { damping: 12, mass: 1.0, stiffness: 80 },
  });
  const corona = interpolate(frame, [40, 60], [0, 1], {
    extrapolateRight: "clamp",
  });
  const kRise = spring({
    frame: frame - 36,
    fps,
    config: { damping: 13, mass: 1.1, stiffness: 95 },
  });
  const wordOp = interpolate(frame, [64, 92], [0, 1], {
    extrapolateRight: "clamp",
  });
  const sunSize = height * 1.4 * sunGrow;
  const eclipseSize = height * 1.4 * eclipse;
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 18,
      }}
    >
      <div
        style={{
          position: "relative",
          width: height * 2,
          height: height * 2,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {/* Sun (teal) */}
        <div
          style={{
            position: "absolute",
            width: sunSize,
            height: sunSize,
            borderRadius: "50%",
            background: `radial-gradient(closest-side, ${TEAL}, ${TEAL}66 50%, transparent 75%)`,
            filter: "blur(2px)",
          }}
        />
        {/* Black eclipse disc */}
        <div
          style={{
            position: "absolute",
            width: eclipseSize,
            height: eclipseSize,
            borderRadius: "50%",
            background: "#000",
            boxShadow: `0 0 80px ${TEAL}88`,
          }}
        />
        {/* Corona ring */}
        <div
          style={{
            position: "absolute",
            width: eclipseSize * 1.05,
            height: eclipseSize * 1.05,
            borderRadius: "50%",
            border: `1px solid ${TEAL}`,
            opacity: corona,
            boxShadow: `0 0 28px ${TEAL}cc`,
          }}
        />
        {/* K rising from below, masked by the disc */}
        <div
          style={{
            position: "absolute",
            transform: `translateY(${(1 - kRise) * height}px)`,
            opacity: kRise,
            filter: `drop-shadow(0 0 18px ${TEAL}66)`,
          }}
        >
          <KMark size={height * 0.85} color="#fff" innerColor="#000" />
        </div>
      </div>
      <div
        style={{
          fontFamily: "Helvetica, Arial, sans-serif",
          fontWeight: 900,
          fontSize: height * 0.85,
          letterSpacing: -height * 0.05,
          lineHeight: 1,
          color: "#fff",
          opacity: wordOp,
        }}
      >
        {WORD}
      </div>
    </div>
  );
};

// =================================================================
// 4) LIQUID — a teal wave sweeps across the frame from left to right;
//    where it has passed, the wordmark is "etched out" of white.
//    A subtle drip animation underlines the wordmark at the end.
// =================================================================
export const LogoLiquid: React.FC<{ height?: number; width?: number }> = ({
  height = 200,
  width = 1500,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // Wave progresses left → right
  const sweep = interpolate(frame, [4, 56], [0, 1], {
    extrapolateRight: "clamp",
  });
  const dripScale = spring({
    frame: frame - 56,
    fps,
    config: { damping: 14, mass: 1.0, stiffness: 110 },
  });
  const settle = interpolate(frame, [60, 80], [0, 1], {
    extrapolateRight: "clamp",
  });
  return (
    <div
      style={{
        position: "relative",
        width,
        height: height * 2,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        overflow: "visible",
      }}
    >
      {/* Wordmark with K monogram inline, masked by the wave */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: height * 0.15,
        }}
      >
        <div
          style={{
            transform: `translateY(${(1 - settle) * 18}px)`,
          }}
        >
          <KMark size={height} color="#fff" innerColor="#000" />
        </div>
        <div
          style={{
            position: "relative",
            display: "inline-flex",
            fontFamily: "Helvetica, Arial, sans-serif",
            fontWeight: 900,
            fontSize: height,
            letterSpacing: -height * 0.06,
            lineHeight: 1,
            color: "#fff",
            transform: `translateY(${(1 - settle) * 18}px)`,
          }}
        >
          {/* Hidden until wave passes */}
          <span style={{ clipPath: `inset(0 ${100 - sweep * 100}% 0 0)` }}>
            {WORD}
          </span>
        </div>
      </div>
      {/* Wave leading edge */}
      <div
        style={{
          position: "absolute",
          top: -height * 0.4,
          bottom: -height * 0.4,
          left: -200,
          width: 240,
          transform: `translateX(${sweep * (width + 240)}px)`,
          background: `linear-gradient(90deg, transparent 0%, ${TEAL}cc 50%, transparent 100%)`,
          filter: "blur(6px)",
          mixBlendMode: "screen",
          boxShadow: `0 0 60px ${TEAL}99`,
        }}
      />
      {/* Drip baseline */}
      <div
        style={{
          position: "absolute",
          bottom: height * 0.35,
          left: 0,
          right: 0,
          height: 2,
          background: TEAL,
          transformOrigin: "left center",
          transform: `scaleX(${dripScale})`,
          boxShadow: `0 0 12px ${TEAL}cc`,
        }}
      />
    </div>
  );
};
