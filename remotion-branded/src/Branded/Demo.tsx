import React from "react";
import {
  AbsoluteFill,
  Sequence,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {
  NightBg,
  HLetterbox,
  WatermarkH,
  Vignette,
  Grain,
  FlashIn,
  TextCard,
} from "./MinimalCommon";
import {
  LogoArchitecture,
  LogoParticles,
  LogoEclipse,
  LogoLiquid,
} from "./LogoSpectacle";

// ============================================================================
// Demo — A neutral 20-second showcase of the four logo reveal systems.
// Replace the WORDMARK constant in LogoSpectacle.tsx and the watermark in
// MinimalCommon.tsx with your own brand to adapt to any campaign.
// ============================================================================

const Slot: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const op = Math.min(
    interpolate(frame, [0, 14], [0, 1], { extrapolateRight: "clamp" }),
    interpolate(
      frame,
      [durationInFrames - 14, durationInFrames],
      [1, 0],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    )
  );
  return (
    <NightBg>
      <FlashIn frames={4} />
      <HLetterbox />
      <WatermarkH />
      <AbsoluteFill
        style={{ justifyContent: "center", alignItems: "center", opacity: op }}
      >
        {children}
      </AbsoluteFill>
      <Vignette strength={0.55} />
      <Grain intensity={0.05} />
    </NightBg>
  );
};

export const Demo: React.FC = () => {
  const { fps } = useVideoConfig();
  const s = (sec: number) => Math.round(sec * fps);
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <Sequence from={s(0)} durationInFrames={s(2)}>
        <TextCard kicker="LOGO SYSTEMS" title={`Four reveals.\nOne primitive set.`} />
      </Sequence>
      <Sequence from={s(2)} durationInFrames={s(5)}>
        <Slot>
          <LogoArchitecture height={170} />
        </Slot>
      </Sequence>
      <Sequence from={s(7)} durationInFrames={s(5)}>
        <Slot>
          <LogoParticles height={170} />
        </Slot>
      </Sequence>
      <Sequence from={s(12)} durationInFrames={s(5)}>
        <Slot>
          <LogoEclipse height={190} />
        </Slot>
      </Sequence>
      <Sequence from={s(17)} durationInFrames={s(5)}>
        <Slot>
          <LogoLiquid height={180} width={1500} />
        </Slot>
      </Sequence>
    </AbsoluteFill>
  );
};
