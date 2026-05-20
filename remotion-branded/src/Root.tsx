import { Composition } from "remotion";
import { Demo } from "./Branded/Demo";

export const FPS = 30;

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="Demo"
      component={Demo}
      durationInFrames={FPS * 22}
      fps={FPS}
      width={1920}
      height={1080}
    />
  </>
);
