import type { ISODateTime, UUID } from "./api";

export const FLOOR_PLAN_DISCLAIMER = "Conceptual Design — Not for Construction.";

export type FloorPlanRunStatus =
  | "queued"
  | "preflighting"
  | "building_context"
  | "generating"
  | "solving"
  | "validating"
  | "completed"
  | "partial"
  | "failed"
  | "cancelled";

export type FloorPlanOptionStatus =
  | "generating"
  | "validating"
  | "valid"
  | "invalid"
  | "accepted"
  | "rejected"
  | "superseded";

export type ConstraintTraceStatus = "satisfied" | "partially_satisfied" | "violated";

export interface FloorPlanFailureBudget {
  maxSolverAttempts: number;
  maxProviderRetries: number;
  maxProcessingSeconds: number;
  maxInvalidCandidates: number;
}

export interface FloorPlanUserConstraint {
  code: string;
  title: string;
  category: string;
  priority: "hard" | "preferred" | "informational";
  value: unknown;
  explanation: string;
}

export interface FloorPlanGenerationRequest {
  optionCount: number;
  deterministicSeed?: number | null;
  preferredStyle?: string | null;
  budgetMode: "economy" | "balanced" | "premium";
  vastuPreference: "not_required" | "preferred" | "strict";
  userConstraints: FloorPlanUserConstraint[];
  diversityThreshold: number;
  failureBudget: FloorPlanFailureBudget;
}

export interface FloorPlanReadinessIssue {
  code: string;
  severity: "blocking" | "warning";
  message: string;
  actionUrl: string | null;
}

export interface FloorPlanReadiness {
  ready: boolean;
  issues: FloorPlanReadinessIssue[];
  projectId: UUID;
  projectVersion: number;
  approvedBriefId: UUID | null;
  approvedBriefVersion: number | null;
  memoryVersionId: UUID | null;
  boundaryVersionId: UUID | null;
  analysisSnapshotId: UUID | null;
  sourceVersions: Record<string, unknown>;
  buildableAreaM2: number | null;
  disclaimer: string;
}

export interface FloorPlanRun {
  id: UUID;
  projectId: UUID;
  status: FloorPlanRunStatus;
  requestedOptionCount: number;
  completedOptionCount: number;
  deterministicSeed: number;
  sourceVersions: Record<string, unknown>;
  engineVersion: string;
  solverVersion: string;
  geometryEngineVersion: string;
  provider: string;
  model: string;
  cacheHit: boolean;
  cacheSourceRunId: UUID | null;
  diversityThreshold: number;
  failureBudget: FloorPlanFailureBudget;
  failureUsage: {
    solverAttempts: number;
    providerRetries: number;
    invalidCandidates: number;
  };
  estimatedInputTokens: number;
  estimatedOutputTokens: number;
  estimatedCostMicrousd: number;
  inputTokens: number;
  outputTokens: number;
  actualCostMicrousd: number;
  failureCode: string | null;
  failureDetails: Record<string, unknown> | null;
  version: number;
  progressPercent: number;
  createdAt: ISODateTime;
  startedAt: ISODateTime | null;
  completedAt: ISODateTime | null;
  disclaimer: string;
}

export interface FloorPlanGenerationAccepted {
  run: FloorPlanRun;
  jobId: UUID;
  statusUrl: string;
  eventsUrl: string;
}

export type FloorPlanPoint = [number, number];

export interface FloorPlanSpace {
  id: string;
  programKey: string;
  name: string;
  type: string;
  zone: "public" | "private" | "service" | "circulation";
  floorIndex: number;
  polygon: FloorPlanPoint[];
  areaM2: number;
}

export interface FloorPlanWall {
  id: string;
  start: FloorPlanPoint;
  end: FloorPlanPoint;
  thicknessMm: number;
  exterior: boolean;
}

export interface FloorPlanOpening {
  id: string;
  floorIndex: number;
  start: FloorPlanPoint;
  end: FloorPlanPoint;
  wallId: string;
  kind?: "entrance" | "internal";
  connects?: string[];
  roomId?: string;
}

export interface FloorPlanCirculation {
  id: string;
  widthMm: number;
  polygon: FloorPlanPoint[];
  areaM2: number;
  paths: Array<{
    id: string;
    widthMm: number;
    points: FloorPlanPoint[];
  }>;
}

export interface FloorPlanFloor {
  index: number;
  name: string;
  elevationMm: number;
  envelope: FloorPlanPoint[];
  rooms: FloorPlanSpace[];
  walls: FloorPlanWall[];
  doors: FloorPlanOpening[];
  windows: FloorPlanOpening[];
  stairs: FloorPlanSpace[];
  parking: FloorPlanSpace[];
  balconies: FloorPlanSpace[];
  circulation: FloorPlanCirculation;
}

export interface FloorPlanGeometry {
  schemaVersion: string;
  coordinateSpace: "local_cartesian";
  unit: "millimeter";
  conceptual: true;
  plotBoundary: FloorPlanPoint[];
  buildableEnvelope: FloorPlanPoint[];
  northIndicatorDegrees: number;
  floors: FloorPlanFloor[];
  adjacencyGraph: {
    nodes: string[];
    edges: [string, string][];
  };
  areaSummary: Record<string, number>;
  coordinateTransform: Record<string, unknown>;
  sourceVersions: Record<string, unknown>;
}

export interface ConstraintTraceItem {
  code: string;
  category: string;
  status: ConstraintTraceStatus;
  severity: "blocking" | "warning" | "informational";
  target: unknown;
  actual: unknown;
  reasonCode: string;
  reason: string;
}

export interface FloorPlanValidation {
  status: "valid" | "invalid";
  validationEngineVersion: string;
  geometryEngineVersion: string;
  summary: Record<string, number>;
  checks: Array<Record<string, unknown>>;
  errors: Array<Record<string, unknown>>;
  warnings: Array<Record<string, unknown>>;
}

export interface FloorPlanOptionSummary {
  id: UUID;
  runId: UUID;
  optionNumber: number;
  status: FloorPlanOptionStatus;
  deterministicSeed: number;
  title: string;
  summary: string;
  majorDecisions: Array<{
    code: string;
    title: string;
    explanation: string;
    confidence: number;
  }>;
  constraintTrace: ConstraintTraceItem[];
  areaSummary: Record<string, number>;
  warnings: Array<Record<string, unknown>>;
  confidence: number;
  topologySignature: string;
  topologyFeatures: Record<string, unknown>;
  diversityScore: number;
  version: number;
  validation: FloorPlanValidation;
  createdAt: ISODateTime;
  disclaimer: string;
}

export interface FloorPlanOption extends FloorPlanOptionSummary {
  geometrySnapshotId: UUID;
  geometryHash: string;
  geometryEngineVersion: string;
  geometry: FloorPlanGeometry;
}

export interface FloorPlanComparisonMetric {
  code: string;
  label: string;
  values: Record<UUID, unknown>;
  bestOptionId: UUID | null;
}

export interface FloorPlanComparison {
  options: FloorPlanOptionSummary[];
  metrics: FloorPlanComparisonMetric[];
  disclaimer: string;
}

export interface FloorPlanDesignVersion {
  id: UUID;
  projectId: UUID;
  sourceRunId: UUID;
  sourceOptionId: UUID;
  geometrySnapshotId: UUID;
  validationResultId: UUID;
  restoredFromDesignVersionId: UUID | null;
  version: number;
  name: string;
  geometryHash: string;
  sourceVersions: Record<string, unknown>;
  engineVersions: Record<string, unknown>;
  versionMetadata: Record<string, unknown>;
  sourceProvider: string;
  sourceModel: string;
  generationCostMicrousd: number;
  generationTimeMs: number | null;
  disclaimer: string;
  acceptedAt: ISODateTime;
  createdAt: ISODateTime;
}

export interface FloorPlanRunEvent {
  id: string;
  runId: UUID;
  sequence: number;
  eventType: string;
  payload: Record<string, unknown>;
  createdAt: ISODateTime;
}
