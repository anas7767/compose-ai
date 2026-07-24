import type { ISODateTime, UUID } from "./api";

export type EditorToolId =
  | "select"
  | "pan"
  | "wall"
  | "room"
  | "door"
  | "window"
  | "stair"
  | "dimension"
  | "label";

export type EditorObjectType =
  | "floor"
  | "room"
  | "wall"
  | "opening"
  | "stair"
  | "dimension"
  | "label"
  | "furniture_placeholder"
  | "structural_placeholder";

export type EditorOperationType =
  | "wall.create"
  | "wall.move"
  | "room.create"
  | "room.update"
  | "opening.create"
  | "opening.update"
  | "stair.create"
  | "object.update"
  | "object.delete"
  | "label.update"
  | "dimension.create"
  | "snapshot.replace";

export type EditorValidationSeverity = "info" | "warning" | "error" | "blocking";
export type EditorInspectorTab = "properties" | "validation" | "metadata" | "history";

export interface EditorPoint {
  x: number;
  y: number;
}

export interface EditorBounds {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

export interface EditorLayer {
  id: string;
  label: string;
  visible: boolean;
  locked: boolean;
  objectCount: number;
}

export interface EditorViewportState {
  zoom: number;
  panX: number;
  panY: number;
  activeFloorId: string | null;
  selectedObjectIds: string[];
  activeTool: EditorToolId;
  snapEnabled: boolean;
  gridVisible: boolean;
}

export interface EditorSnapSettings {
  enabled: boolean;
  grid: boolean;
  corner: boolean;
  wallIntersection: boolean;
  parallel: boolean;
  perpendicular: boolean;
  center: boolean;
  equalSpacingGuides: boolean;
}

export interface EditorMeasurementOverlay {
  length: number | null;
  angle: number | null;
  distance: number | null;
  area: number | null;
  unit: string;
}

export interface EditorToolDefinition {
  id: EditorToolId;
  label: string;
  shortcut: string | null;
  cursor: string;
  pluginKey: string;
  supportedObjectTypes: EditorObjectType[];
}

export interface EditorObject {
  id: string;
  type: EditorObjectType;
  floorId: string;
  layerId: string;
  name: string | null;
  points: EditorPoint[];
  wallId: string | null;
  position: number | null;
  width: number | null;
  height: number | null;
  metadata: Record<string, unknown>;
  revisionCreated: number;
  revisionUpdated: number;
  deleted: boolean;
}

export interface EditorFloor {
  id: string;
  index: number;
  name: string;
  elevationMm: number;
  bounds: EditorBounds;
}

export interface EditorValidationIssue {
  id: string;
  code: string;
  severity: EditorValidationSeverity;
  objectId: string | null;
  objectType: EditorObjectType | null;
  message: string;
  reason: string;
  blocking: boolean;
}

export interface EditorValidationSummary {
  status: "valid" | "invalid";
  issueCount: number;
  blockingCount: number;
  errorCount: number;
  warningCount: number;
  infoCount: number;
}

export interface EditorSnapshot {
  schemaVersion: string;
  unit: string;
  coordinateSpace: string;
  floors: EditorFloor[];
  objects: EditorObject[];
  layers: EditorLayer[];
  snapSettings: EditorSnapSettings;
  measurementOverlay: EditorMeasurementOverlay | null;
  source: Record<string, unknown>;
}

export interface EditorOperation {
  clientOperationId: string;
  type: EditorOperationType;
  objectId: string | null;
  payload: Record<string, unknown>;
  createdAt: ISODateTime;
}

export interface EditorOperationBatchRequest {
  baseRevision: number;
  clientBatchId: string;
  operations: EditorOperation[];
}

export interface EditorOperationBatchResponse {
  projectId: UUID;
  editorDocumentId: UUID;
  previousRevision: number;
  currentRevision: number;
  appliedOperationIds: string[];
  validationSummary: EditorValidationSummary;
  snapshotHash: string;
}

export interface EditorValidationResponse {
  projectId: UUID;
  editorDocumentId: UUID;
  revision: number;
  validationEngineVersion: string;
  geometryEngineVersion: string;
  summary: EditorValidationSummary;
  issues: EditorValidationIssue[];
}

export interface EditorCheckpoint {
  id: UUID;
  projectId: UUID;
  editorDocumentId: UUID;
  sourceRevision: number;
  name: string;
  kind: string;
  snapshotHash: string;
  validationSummary: EditorValidationSummary;
  metadata: Record<string, unknown>;
  createdAt: ISODateTime;
}

export interface EditorHistoryItem {
  id: UUID;
  itemType: "operation_batch" | "checkpoint";
  title: string;
  revision: number;
  operationCount: number;
  checkpointKind: string | null;
  createdAt: ISODateTime;
}

export interface EditorHistory {
  items: EditorHistoryItem[];
}

export interface EditorDocument {
  id: UUID;
  projectId: UUID;
  sourceDesignVersionId: UUID;
  sourceGeometrySnapshotId: UUID;
  status: string;
  currentRevision: number;
  schemaVersion: string;
  rendererContractVersion: string;
  snapshotHash: string;
  snapshot: EditorSnapshot;
  validationSummary: EditorValidationSummary;
  validationIssues: EditorValidationIssue[];
  viewState: EditorViewportState;
  layers: EditorLayer[];
  toolRegistry: EditorToolDefinition[];
  inspectorTabs: EditorInspectorTab[];
  history: EditorHistoryItem[];
  autosave: Record<string, unknown>;
  disclaimer: string;
  updatedAt: ISODateTime;
}
