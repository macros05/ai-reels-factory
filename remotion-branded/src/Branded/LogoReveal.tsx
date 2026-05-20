import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

/**
 * Logo reveal primitives inspired by the brand reference reel:
 *
 *   - SlotReveal     : letters rise from below clipped by a horizontal slot
 *                      (the "emerging through a slit" look from frame 1s).
 *   - WipeReveal     : a horizontal bar sweeps L→R uncovering the wordmark.
 *   - LetterAssemble : each letter springs in staggered with vertical jitter.
 *   - GiantBg        : a single oversized letterform sits in the background
 *                      (the "K shape behind the manifesto" frame 13s look).
 *
 * Reusable across compositions. Drop in instead of <Img src={logoSrc} />.
 */

const WORDMARK = "BRAND";

const Mark: React.FC<{ size: number; color?: string }> = ({ size, color = "#fff" }) => (
  // The K-in-circle icon, rendered from scratch in SVG so we can animate strokes
  // and keep it pin-sharp at any scale.
  <svg width={size} height={size} viewBox="0 0 100 100" style={{ flexShrink: 0 }}>
    <circle cx={50} cy={50} r={47} fill={color} />
    <path
      d="M 30 30 L 70 30 L 70 70 L 30 70 Z M 30 30 L 70 70"
      stroke="#000"
      strokeWidth={5}
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

// ---------------------------------------------------------------------------
// Slot reveal — letters appear to rise THROUGH a horizontal slit.
// Each letter sits in a clip-rect that only shows the band where it intersects
// the slot, then translates up to its rest position. Mirrors the ref frame 1s.
// ---------------------------------------------------------------------------

export const SlotReveal: React.FC<{
  height?: number;
  letterSpacing?: number;
  fontWeight?: number;
  showMark?: boolean;
  delayPerLetter?: number;
  width?: number;
}> = ({ height = 200, letterSpacing = -8, fontWeight = 900, showMark = true, delayPerLetter = 3, width = 920 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const slotH = Math.round(height * 1.05);
  const letters = WORDMARK.split("");
  return (
    <div style={{ display: "flex", alignItems: "center", gap: height * 0.15 }}>
      {showMark && (
        <SlotItem delay={0} h={slotH} fps={fps} frame={frame}>
          <Mark size={height} />
        </SlotItem>
      )}
      <div style={{ display: "flex" }}>
        {letters.map((L, i) => (
          <SlotItem key={i} delay={(i + 1) * delayPerLetter} h={slotH} fps={fps} frame={frame}>
            <span
              style={{
                fontSize: height,
                fontFamily: "Helvetica, Arial, sans-serif",
                fontWeight,
                letterSpacing,
                lineHeight: 1,
                color: "#fff",
                display: "inline-block",
              }}
            >
              {L}
            </span>
          </SlotItem>
        ))}
      </div>
    </div>
  );
};

const SlotItem: React.FC<{ delay: number; h: number; fps: number; frame: number; children: React.ReactNode }> = ({ delay, h, fps, frame, children }) => {
  const local = Math.max(0, frame - delay);
  const s = spring({ frame: local, fps, config: { damping: 12, mass: 0.7, stiffness: 120 } });
  const y = (1 - s) * h * 1.1;
  return (
    <div
      style={{
        height: h,
        overflow: "hidden",
        display: "inline-flex",
        alignItems: "flex-end",
      }}
    >
      <div style={{ transform: `translateY(${y}px)` }}>{children}</div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Wipe reveal — a black bar slides L→R unveiling the wordmark behind.
// ---------------------------------------------------------------------------

export const WipeReveal: React.FC<{ height?: number; showMark?: boolean; durationFrames?: number }> = ({
  height = 180,
  showMark = true,
  durationFrames = 36,
}) => {
  const frame = useCurrentFrame();
  const progress = interpolate(frame, [4, durationFrames], [0, 100], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <div style={{ position: "relative", display: "flex", alignItems: "center", gap: height * 0.15 }}>
      {showMark && <Mark size={height} />}
      <div
        style={{
          fontSize: height,
          fontFamily: "Helvetica, Arial, sans-serif",
          fontWeight: 900,
          letterSpacing: -8,
          lineHeight: 1,
          color: "#fff",
          clipPath: `inset(0 ${100 - progress}% 0 0)`,
        }}
      >
        {WORDMARK}
      </div>
      {/* the moving bar that's wiping */}
      <div
        style={{
          position: "absolute",
          top: -10,
          bottom: -10,
          left: `${(showMark ? height + height * 0.15 : 0) + (progress / 100) * (height * 4.4)}px`,
          width: 6,
          background: "#fff",
          boxShadow: "0 0 30px rgba(255,255,255,0.7)",
          opacity: progress >= 99 ? 0 : 1,
          transition: "opacity 0.1s",
        }}
      />
    </div>
  );
};

// ---------------------------------------------------------------------------
// Letter assemble — each character springs in with vertical jitter + rotation.
// ---------------------------------------------------------------------------

export const LetterAssemble: React.FC<{ height?: number; showMark?: boolean; delayPerLetter?: number }> = ({
  height = 180,
  showMark = true,
  delayPerLetter = 3,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <div style={{ display: "flex", alignItems: "center", gap: height * 0.15 }}>
      {showMark && (
        <SpringWrap delay={0} fps={fps} frame={frame} fromY={-height * 0.5}>
          <Mark size={height} />
        </SpringWrap>
      )}
      <div style={{ display: "flex" }}>
        {WORDMARK.split("").map((L, i) => (
          <SpringWrap key={i} delay={(i + 1) * delayPerLetter} fps={fps} frame={frame} fromY={height * 0.6} flipRot={i % 2 === 0}>
            <span
              style={{
                fontSize: height,
                fontFamily: "Helvetica, Arial, sans-serif",
                fontWeight: 900,
                letterSpacing: -8,
                lineHeight: 1,
                color: "#fff",
              }}
            >
              {L}
            </span>
          </SpringWrap>
        ))}
      </div>
    </div>
  );
};

const SpringWrap: React.FC<{
  delay: number;
  fps: number;
  frame: number;
  fromY: number;
  flipRot?: boolean;
  children: React.ReactNode;
}> = ({ delay, fps, frame, fromY, flipRot, children }) => {
  const local = Math.max(0, frame - delay);
  const s = spring({ frame: local, fps, config: { damping: 9, mass: 0.7, stiffness: 200 } });
  const y = (1 - s) * fromY;
  const rot = (1 - s) * (flipRot ? -8 : 8);
  return (
    <span style={{ display: "inline-block", transform: `translateY(${y}px) rotate(${rot}deg)`, opacity: s }}>{children}</span>
  );
};

// ---------------------------------------------------------------------------
// GiantBg — an oversized single letter sits behind a child element.
// Mirrors the "huge K shape behind the manifesto text" from ref frame 13s.
// ---------------------------------------------------------------------------

export const GiantBg: React.FC<{ letter?: string; opacity?: number; size?: number; children?: React.ReactNode; parallax?: boolean }> = ({
  letter = "K",
  opacity = 0.12,
  size = 1400,
  children,
  parallax = true,
}) => {
  const frame = useCurrentFrame();
  const drift = parallax ? interpolate(frame, [0, 120], [-30, 30]) : 0;
  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          inset: 0,
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
            color: "#fff",
            opacity,
            letterSpacing: -size * 0.05,
            lineHeight: 0.8,
            transform: `translate(${drift}px, 0)`,
            textShadow: "0 0 80px rgba(255,255,255,0.1)",
          }}
        >
          {letter}
        </span>
      </div>
      {children}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// Convenience wrapper to pick a mode by prop. Default centered in screen.
// ---------------------------------------------------------------------------

export type LogoMode = "slot" | "wipe" | "assemble";

export const LogoReveal: React.FC<{ mode?: LogoMode; height?: number; showMark?: boolean }> = ({
  mode = "slot",
  height = 180,
  showMark = true,
}) => {
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      {mode === "slot" && <SlotReveal height={height} showMark={showMark} />}
      {mode === "wipe" && <WipeReveal height={height} showMark={showMark} />}
      {mode === "assemble" && <LetterAssemble height={height} showMark={showMark} />}
    </AbsoluteFill>
  );
};
