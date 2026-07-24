import type {
  SceneCameraPreset,
  SceneClipBox,
  SceneEnvironmentPreset,
  SceneMaterial,
  SceneObject,
  SceneQualityPreset,
} from "@compose-ai/shared";

export interface SceneRendererProps {
  cameraPresetId: string;
  environmentPreset: SceneEnvironmentPreset;
  materials: SceneMaterial[];
  objects: SceneObject[];
  onObjectSelect: (sourceObjectId: string | null, stableObjectId: string) => void;
  qualityPreset: SceneQualityPreset;
  roofVisible: boolean;
  sectionBox: SceneClipBox;
  selectedSourceObjectId: string | null;
  wallOpacity: number;
}

export interface SceneRendererShellProps extends SceneRendererProps {
  cameraPresets: SceneCameraPreset[];
}
