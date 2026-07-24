import type { ISODateTime, UUID } from "./api";

export type AIThreadStatus = "active" | "archived";
export type AIMessageMode = "advice" | "proposal";
export type AIMessageRole = "user" | "assistant" | "system_internal" | "tool_internal";
export type AIMessageStatus = "pending" | "streaming" | "completed" | "failed";
export type AIRunType = "architect_chat" | "architect_brief" | "requirement_normalization";
export type AIRunStatus = "queued" | "running" | "completed" | "failed" | "cancelled";
export type AIBriefStatus =
  | "generating"
  | "proposed"
  | "under_review"
  | "approved"
  | "applied"
  | "rejected"
  | "superseded"
  | "failed";
export type AIProposalStatus = "pending" | "approved" | "rejected" | "applied" | "stale";
export type AIProposalTarget =
  | "project_field"
  | "requirements_field"
  | "room_requirements"
  | "plot_recommendation";

export interface AIThread {
  id: UUID;
  projectId: UUID;
  title: string;
  status: AIThreadStatus;
  version: number;
  messageCount: number;
  lastMessageAt: ISODateTime | null;
  createdAt: ISODateTime;
  updatedAt: ISODateTime;
}

export interface AIMessage {
  id: UUID;
  threadId: UUID;
  runId: UUID | null;
  role: AIMessageRole;
  mode: AIMessageMode;
  sequenceNumber: number;
  content: string;
  status: AIMessageStatus;
  createdAt: ISODateTime;
}

export interface AIRun {
  id: UUID;
  projectId: UUID;
  threadId: UUID | null;
  runType: AIRunType;
  status: AIRunStatus;
  provider: string;
  modelAlias: string;
  estimatedInputTokens: number;
  estimatedOutputTokens: number;
  estimatedCostMicrousd: number;
  inputTokens: number;
  outputTokens: number;
  actualCostMicrousd: number;
  cacheHit: boolean;
  failureCode: string | null;
  failureDetails: Record<string, unknown> | null;
  createdAt: ISODateTime;
  startedAt: ISODateTime | null;
  completedAt: ISODateTime | null;
}

export interface AIMessageAccepted {
  message: AIMessage;
  run: AIRun;
  streamUrl: string;
}

export interface AIBriefAccepted {
  run: AIRun;
  jobId: UUID;
  statusUrl: string;
}

export interface AIRunRetry {
  run: AIRun;
  jobId: UUID | null;
  streamUrl: string | null;
}

export interface AISourceReference {
  source_type: string;
  source_id?: string | null;
  field_path?: string | null;
  excerpt?: string | null;
}

export interface AIBriefGoal {
  title: string;
  description: string;
  confidence: number;
  source_references: AISourceReference[];
}

export interface AIBriefPriority extends AIBriefGoal {
  rank: number;
  category: string;
  confirmed: boolean;
}

export interface AIBriefConstraint extends AIBriefGoal {
  category: string;
  constraint_type: "hard" | "preferred" | "informational" | "unresolved";
}

export interface AIMissingInformation {
  topic: string;
  reason: string;
  blocking: boolean;
  priority: "high" | "medium" | "low";
  expected_answer: string;
  target_path?: string | null;
}

export interface AIBriefConflict {
  title: string;
  description: string;
  severity: "blocking" | "warning" | "informational";
  suggested_resolution: string;
  affected_paths: string[];
  source_references: AISourceReference[];
}

export interface AIClarificationQuestion {
  question: string;
  reason: string;
  priority: number;
  target_path?: string | null;
}

export interface AINextStep {
  title: string;
  description: string;
  priority: number;
}

export interface AIBriefWarning {
  code: string;
  message: string;
  target_path?: string | null;
}

export interface AIBriefAssumption {
  statement: string;
  reason: string;
  confidence: number;
}

export interface AIProposal {
  id: UUID;
  briefVersionId: UUID;
  targetType: AIProposalTarget;
  targetPath: string;
  existingValue: unknown;
  proposedValue: unknown;
  explanation: string;
  confidence: number;
  sourceReferences: AISourceReference[];
  warnings: AIBriefWarning[];
  status: AIProposalStatus;
  expectedProjectVersion: number;
  reviewedAt: ISODateTime | null;
  appliedAt: ISODateTime | null;
}

export interface AIBrief {
  id: UUID;
  projectId: UUID;
  version: number;
  sourceRunId: UUID;
  status: AIBriefStatus;
  originalInput: string;
  summary: string;
  goals: AIBriefGoal[];
  priorities: AIBriefPriority[];
  constraints: AIBriefConstraint[];
  normalizedRequirements: Record<string, unknown>;
  missingInformation: AIMissingInformation[];
  conflicts: AIBriefConflict[];
  clarificationQuestions: AIClarificationQuestion[];
  recommendedNextSteps: AINextStep[];
  warnings: AIBriefWarning[];
  assumptions: AIBriefAssumption[];
  aggregateConfidence: number;
  basedOnProjectVersion: number;
  approvedAt: ISODateTime | null;
  appliedAt: ISODateTime | null;
  createdAt: ISODateTime;
  proposals: AIProposal[];
}

export interface AIMemory {
  id: UUID;
  version: number;
  projectVersion: number;
  contextSummary: string;
  includedSources: Array<Record<string, unknown>>;
  redactionSummary: Record<string, unknown>;
  tokenEstimate: number;
  contextHash: string;
  schemaVersion: string;
  createdAt: ISODateTime;
}

export interface AIUsage {
  periodStart: string;
  periodEnd: string;
  inputTokens: number;
  outputTokens: number;
  costMicrousd: number;
  runCount: number;
  cacheHitCount: number;
  dailyCostLimitMicrousd: number;
  monthlyCostLimitMicrousd: number;
}

export interface AISuggestedPrompt {
  id: string;
  label: string;
  prompt: string;
  mode: AIMessageMode;
}

export interface AIRunEvent {
  id: string;
  runId: UUID;
  sequence: number;
  eventType: string;
  payload: Record<string, unknown>;
  createdAt: ISODateTime;
}

export interface AIThreadCreateRequest {
  title?: string;
}

export interface AIMessageCreateRequest {
  content: string;
  mode: AIMessageMode;
  clientMessageId: string;
}

export interface AIBriefGenerateRequest {
  rawRequirements: string;
  threadId?: UUID | null;
}

export interface AIProposalApplyResponse {
  projectId: UUID;
  projectVersion: number;
  appliedProposalIds: UUID[];
  briefStatus: AIBriefStatus;
}
