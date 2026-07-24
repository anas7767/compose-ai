export const EXTERIOR_DESIGN_DISCLAIMER = "Conceptual Design — Not for Construction.";

export type ExteriorDesignRunStatus =
  | "pending"
  | "queued"
  | "running"
  | "succeeded"
  | "partially_succeeded"
  | "failed"
  | "cancelled"
  | "rate_limited"
  | "timed_out";

export type ExteriorDesignStyle =
  | "modern"
  | "contemporary"
  | "minimal"
  | "traditional"
  | "tropical"
  | "colonial"
  | "industrial";

export type ExteriorDesignViewType = "front" | "left" | "right" | "rear";
export type ExteriorApprovalStatus = "pending" | "approved" | "rejected";
export type ExteriorOptionStatus = "generated" | "valid" | "invalid" | "approved" | "rejected" | "hidden";
export type ExteriorValidationStatus = "valid" | "invalid";
export type ExteriorMaterialCategory =
  | "paint"
  | "brick"
  | "concrete"
  | "marble"
  | "granite"
  | "wood"
  | "glass"
  | "metal"
  | "tiles";

export interface ExteriorReadinessIssue {
  code: string;
  severity: "blocking" | "warning";
  message: string;
  actionUrl: string | null;
}

export interface ExteriorReadiness {
  ready: boolean;
  projectId: string;
  sourceDesignVersionId: string | null;
  sourceSceneVersionId: string | null;
  sourceEditorCheckpointId: string | null;
  sourceBriefId: string | null;
  materialLibrary: ExteriorMaterialCategory[];
  supportedStyles: ExteriorDesignStyle[];
  supportedViews: ExteriorDesignViewType[];
  issues: ExteriorReadinessIssue[];
  disclaimer: string;
}

export interface ExteriorGenerationRequest {
  style: ExteriorDesignStyle;
  viewType: ExteriorDesignViewType;
  materialPreferences: ExteriorMaterialCategory[];
  optionCount: number;
  userInstructions?: string | null;
  negativeConstraints?: string | null;
  seed?: number | null;
}

export interface ExteriorAsset {
  id: string;
  optionId: string;
  storageProvider: string;
  storageKey: string;
  thumbnailStorageKey: string | null;
  mimeType: string;
  width: number;
  height: number;
  byteSize: number;
  integrityHash: string;
  deliveryReference: string;
  createdAt: string;
}

export interface ExteriorValidationResult {
  id: string;
  optionId: string;
  status: ExteriorValidationStatus;
  validationEngineVersion: string;
  summary: Record<string, unknown>;
  issues: Array<Record<string, unknown>>;
  createdAt: string;
}

export interface ExteriorOption {
  id: string;
  runId: string;
  projectId: string;
  optionNumber: number;
  style: ExteriorDesignStyle;
  viewType: ExteriorDesignViewType;
  title: string;
  explanation: string;
  status: ExteriorOptionStatus;
  approvalStatus: ExteriorApprovalStatus;
  isConceptual: boolean;
  disclaimer: string;
  sourceDesignVersionId: string;
  sourceSceneVersionId: string;
  sourceEditorCheckpointId: string;
  sourceVersions: Record<string, unknown>;
  safetyMetadata: Record<string, unknown>;
  asset: ExteriorAsset | null;
  validation: ExteriorValidationResult | null;
  createdAt: string;
  updatedAt: string;
  approvedAt: string | null;
  rejectedAt: string | null;
  deletedAt: string | null;
}

export interface ExteriorRun {
  id: string;
  projectId: string;
  status: ExteriorDesignRunStatus;
  provider: string;
  model: string;
  promptVersion: string;
  engineVersion: string;
  requestedOptionCount: number;
  completedOptionCount: number;
  style: ExteriorDesignStyle;
  viewType: ExteriorDesignViewType;
  materialPreferences: ExteriorMaterialCategory[];
  seed: number | null;
  cacheHit: boolean;
  cacheSourceRunId: string | null;
  failureCode: string | null;
  safeFailureMessage: string | null;
  inputTokens: number;
  outputTokens: number;
  costMicrousd: number;
  sourceDesignVersionId: string;
  sourceSceneVersionId: string;
  sourceEditorCheckpointId: string;
  contextHash: string;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
  cancelledAt: string | null;
  disclaimer: string;
}

export interface ExteriorRunDetail extends ExteriorRun {
  options: ExteriorOption[];
}

export interface ExteriorRunEvent {
  id: string;
  runId: string;
  sequence: number;
  eventType: string;
  payload: Record<string, unknown>;
  createdAt: string;
}

export interface ExteriorGenerationAccepted {
  run: ExteriorRun;
  statusUrl: string;
  eventsUrl: string;
}
