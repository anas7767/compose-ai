import type { ISODateTime, UUID } from "./api";
import type { PlotShape, RoadDirection, UnitSystem } from "./projects";

export type CoordinateSpace = "local_cartesian" | "wgs84";
export type NorthReference = "true" | "magnetic" | "assumed";
export type BoundarySource = "manual_vertices" | "geojson_import" | "restore" | "undo" | "clear";
export type PlotIssueSeverity = "error" | "warning" | "info";

export interface GeoJsonPolygon {
  type: "Polygon";
  coordinates: number[][][];
}

export interface PlotRoadSide {
  id: UUID;
  boundaryEdgeIndex: number | null;
  label: string;
  direction: RoadDirection;
  isPrimary: boolean;
  roadName: string | null;
  roadWidth: number | null;
  accessAllowed: boolean;
  sortOrder: number;
}

export interface PlotRoadSideInput {
  id?: UUID;
  boundaryEdgeIndex?: number | null;
  label: string;
  direction: RoadDirection;
  isPrimary: boolean;
  roadName?: string | null;
  roadWidth?: number | null;
  accessAllowed: boolean;
  sortOrder: number;
}

export interface PlotBoundaryInput {
  coordinateSpace: CoordinateSpace;
  geojson: GeoJsonPolygon;
  source: "manual_vertices" | "geojson_import";
}

export interface PlotBoundaryVersion {
  id: UUID;
  version: number;
  previousBoundaryVersionId: UUID | null;
  restoredFromVersionId: UUID | null;
  coordinateSpace: CoordinateSpace;
  geojson: GeoJsonPolygon | null;
  isTombstone: boolean;
  source: BoundarySource;
  schemaVersion: number;
  geometryEngineVersion: string;
  checksum: string;
  vertexCount: number;
  area: number | null;
  perimeter: number | null;
  boundingBox: Record<string, number> | null;
  centroid: Record<string, number> | null;
  validationStatus: "valid" | "warning" | "not_captured";
  validationDetails: PlotValidationIssue[];
  createdBy: UUID | null;
  createdAt: ISODateTime;
}

export interface PlotValidationIssue {
  code: string;
  severity: PlotIssueSeverity;
  field: string;
  message: string;
  details: Record<string, unknown>;
}

export interface PlotAnalysis {
  id: UUID | null;
  profileRevision: number;
  boundaryVersionId: UUID | null;
  analysisEngineVersion: string;
  geometryEngineVersion: string;
  inputChecksum: string;
  plotCompleteness: number;
  plotHealthScore: number;
  plotHealthStatus: "insufficient_data" | "excellent" | "good" | "needs_review" | "invalid";
  feasibilityStatus:
    | "insufficient_data"
    | "preliminarily_feasible"
    | "constrained"
    | "invalid"
    | "professional_review_required";
  preRegulationBuildableArea: number | null;
  parkingStatus: "not_required" | "likely" | "constrained" | "indeterminate";
  parkingConfidence: "high" | "medium" | "low";
  parkingDetails: Record<string, unknown>;
  coverageStatus: "awaiting_building_footprint";
  coverageDetails: Record<string, unknown>;
  regulationStatus: "not_configured";
  regulationContext: Record<string, unknown>;
  validationSummary: {
    errorCount: number;
    warningCount: number;
    infoCount: number;
    highestSeverity: "error" | "warning" | "none";
  };
  siteSummary: Record<string, unknown>;
  issues: PlotValidationIssue[];
  createdAt: ISODateTime | null;
}

export interface PlotProfile {
  unitSystem: UnitSystem;
  plotLength: number | null;
  plotWidth: number | null;
  plotArea: number | null;
  areaSource: "unknown" | "declared" | "dimensions" | "boundary";
  plotShape: PlotShape | null;
  openSides: number;
  cornerPlot: boolean;
  orientationDegrees: number | null;
  northRotationDegrees: number | null;
  northReference: NorthReference | null;
  profileRevision: number;
}

export interface PlotUndoAction {
  id: UUID;
  restoredBoundaryVersionId: UUID;
  previousActiveBoundaryVersionId: UUID | null;
  expiresAt: ISODateTime;
}

export interface PlotIntelligence {
  projectId: UUID;
  projectName: string;
  projectVersion: number;
  canEdit: boolean;
  profile: PlotProfile;
  roadSides: PlotRoadSide[];
  boundary: PlotBoundaryVersion | null;
  analysis: PlotAnalysis;
  activeUndo: PlotUndoAction | null;
}

export interface PlotProfileUpdateRequest {
  unitSystem?: UnitSystem;
  plotLength?: number | null;
  plotWidth?: number | null;
  plotArea?: number | null;
  plotShape?: PlotShape | null;
  openSides?: number;
  cornerPlot?: boolean;
  orientationDegrees?: number | null;
  northRotationDegrees?: number | null;
  northReference?: NorthReference | null;
  roadSides?: PlotRoadSideInput[];
  boundary?: PlotBoundaryInput | null;
}

export interface PlotRestoreResponse {
  plot: PlotIntelligence;
  undo: PlotUndoAction;
}
