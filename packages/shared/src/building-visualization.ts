export type SceneStatus = "active" | "stale" | "archived";

export type SceneJobStatus =
  | "queued"
  | "validating_source"
  | "compiling_geometry"
  | "generating_materials"
  | "validating_scene"
  | "saving_scene"
  | "completed"
  | "failed"
  | "cancelled";

export type SceneObjectKind =
  | "building"
  | "floor"
  | "room"
  | "wall"
  | "door"
  | "window"
  | "stair"
  | "slab"
  | "roof"
  | "balcony"
  | "parking"
  | "plot_boundary";

export type SceneMaterialCategory =
  | "paint"
  | "brick"
  | "concrete"
  | "marble"
  | "granite"
  | "wood"
  | "glass"
  | "metal"
  | "tiles";

export type SceneEnvironmentPreset = "morning" | "noon" | "evening" | "night";
export type SceneQualityPreset = "low" | "balanced" | "high";

export type SceneVector3 = {
  x: number;
  y: number;
  z: number;
};

export type SceneBoundingBox = {
  min: SceneVector3;
  max: SceneVector3;
};

export type SceneTransform = {
  position: SceneVector3;
  rotation: SceneVector3;
  scale: SceneVector3;
};

export type SceneGeometry = {
  kind: "box" | "extrusion" | "plane" | "polyline" | "placeholder";
  vertices: SceneVector3[];
  indices: number[];
  dimensions: Record<string, number>;
  sourcePolygon: Array<{ x: number; y: number }>;
};

export type SceneMaterial = {
  materialId: string;
  name: string;
  category: SceneMaterialCategory;
  color: string;
  opacity: number;
  roughness: number;
  metalness: number;
  transparent: boolean;
  properties: Record<string, unknown>;
};

export type SceneObject = {
  id: string;
  stableObjectId: string;
  source2dObjectId: string | null;
  source2dObjectType: string | null;
  objectType: SceneObjectKind;
  floorId: string | null;
  parentObjectId: string | null;
  name: string;
  geometryKind: string;
  transform: SceneTransform;
  geometry: SceneGeometry;
  boundingBox: SceneBoundingBox;
  materialId: string;
  triangleCount: number;
  metadata: Record<string, unknown>;
};

export type SceneCamera = {
  position: SceneVector3;
  target: SceneVector3;
  fov: number;
};

export type SceneCameraPreset = {
  id: string;
  label: string;
  camera: SceneCamera;
};

export type SceneLighting = {
  environmentPreset: SceneEnvironmentPreset;
  ambientIntensity: number;
  sunIntensity: number;
  sunDirection: SceneVector3;
  background: string;
};

export type SceneClipBox = {
  enabled: boolean;
  minX?: number | null;
  maxX?: number | null;
  minY?: number | null;
  maxY?: number | null;
  minZ?: number | null;
  maxZ?: number | null;
};

export type SceneGraphNode = {
  id: string;
  label: string;
  objectType: string;
  source2dObjectId: string | null;
  children: SceneGraphNode[];
};

export type SceneValidationIssue = {
  id: string;
  code: string;
  severity: "info" | "warning" | "error" | "blocking";
  objectId: string | null;
  source2dObjectId: string | null;
  message: string;
  reason: string;
  blocking: boolean;
};

export type SceneValidationSummary = {
  status: "valid" | "invalid";
  issueCount: number;
  blockingCount: number;
  errorCount: number;
  warningCount: number;
  infoCount: number;
};

export type SceneManifest = {
  sceneVersionId: string;
  projectId: string;
  sourceDesignVersionId: string;
  sourceEditorDocumentId: string;
  sourceEditorCheckpointId: string;
  sourceEditorRevision: number;
  sceneSchemaVersion: string;
  geometryEngineVersion: string;
  sceneEngineVersion: string;
  materialSchemaVersion: string;
  rendererContractVersion: string;
  unit: string;
  coordinateSpace: string;
  boundingBox: SceneBoundingBox;
  objectCount: number;
  triangleCount: number;
  cameraPresets: SceneCameraPreset[];
  lighting: SceneLighting;
  environmentPresets: SceneEnvironmentPreset[];
  qualityPresets: SceneQualityPreset[];
  sectionBox: SceneClipBox;
  sourceVersions: Record<string, unknown>;
  disclaimer: string;
};

export type SceneVersion = {
  id: string;
  projectId: string;
  version: number;
  status: SceneStatus;
  isStale: boolean;
  manifest: SceneManifest;
  validationSummary: SceneValidationSummary;
  createdAt: string;
  updatedAt: string;
  disclaimer: string;
};

export type SceneCompilationJob = {
  id: string;
  projectId: string;
  status: SceneJobStatus;
  progress: number;
  sourceEditorCheckpointId: string;
  sourceEditorRevision: number;
  sceneVersionId: string | null;
  failureCode: string | null;
  failureDetails: Record<string, unknown> | null;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
  cancelledAt: string | null;
};

export type SceneWorkspace = {
  projectId: string;
  activeScene: SceneVersion | null;
  latestJob: SceneCompilationJob | null;
  hasValidatedCheckpoint: boolean;
  sourceCheckpointId: string | null;
  sourceEditorRevision: number | null;
  isStale: boolean;
  materialLibrary: SceneMaterial[];
  sceneGraph: SceneGraphNode[];
  emptyReason: string | null;
  disclaimer: string;
};

export type SceneObjectsResponse = {
  sceneVersionId: string;
  objects: SceneObject[];
  graph: SceneGraphNode[];
};

export type SceneMaterialsResponse = {
  sceneVersionId: string;
  materials: SceneMaterial[];
  library: SceneMaterial[];
};

export type SceneCameraView = {
  id: string;
  sceneVersionId: string;
  name: string;
  camera: SceneCamera;
  createdAt: string;
};

export type SceneCameraViewsResponse = {
  views: SceneCameraView[];
};

export type SceneCompileRequest = {
  checkpointId?: string | null;
  qualityPreset: SceneQualityPreset;
};
