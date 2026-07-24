import type {
  ApiEnvelope,
  ApiErrorBody,
  EditorCheckpoint,
  EditorDocument,
  EditorHistory,
  EditorOperationBatchRequest,
  EditorOperationBatchResponse,
  EditorSnapshot,
  EditorValidationResponse,
} from "@compose-ai/shared";

import { apiBaseUrl } from "./config";

export class FloorPlanEditorApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "FloorPlanEditorApiError";
  }
}

async function editorRequest<TData>(
  path: string,
  token: string,
  init: RequestInit = {},
): Promise<TData> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...init.headers,
    },
  });
  if (!response.ok) throw await responseError(response);
  return ((await response.json()) as ApiEnvelope<TData>).data;
}

export function getEditorDocument(token: string, projectId: string, signal?: AbortSignal) {
  return editorRequest<EditorDocument>(`/projects/${projectId}/editor`, token, { signal });
}

export function getEditorSnapshot(token: string, projectId: string, signal?: AbortSignal) {
  return editorRequest<EditorSnapshot>(`/projects/${projectId}/editor/snapshot`, token, { signal });
}

export function applyEditorOperations(
  token: string,
  projectId: string,
  request: EditorOperationBatchRequest,
  idempotencyKey: string,
) {
  return editorRequest<EditorOperationBatchResponse>(`/projects/${projectId}/editor/operations`, token, {
    body: JSON.stringify(request),
    headers: { "Idempotency-Key": idempotencyKey },
    method: "POST",
  });
}

export function validateEditorDocument(token: string, projectId: string, snapshot?: EditorSnapshot) {
  return editorRequest<EditorValidationResponse>(`/projects/${projectId}/editor/validate`, token, {
    body: JSON.stringify({ snapshot: snapshot ?? null }),
    method: "POST",
  });
}

export function createEditorCheckpoint(token: string, projectId: string, name: string) {
  return editorRequest<EditorCheckpoint>(`/projects/${projectId}/editor/checkpoints`, token, {
    body: JSON.stringify({ name }),
    headers: { "Idempotency-Key": crypto.randomUUID() },
    method: "POST",
  });
}

export function restoreEditorCheckpoint(token: string, projectId: string, checkpointId: string) {
  return editorRequest<EditorDocument>(
    `/projects/${projectId}/editor/checkpoints/${checkpointId}/restore`,
    token,
    {
      headers: { "Idempotency-Key": crypto.randomUUID() },
      method: "POST",
    },
  );
}

export function getEditorHistory(token: string, projectId: string, signal?: AbortSignal) {
  return editorRequest<EditorHistory>(`/projects/${projectId}/editor/revisions`, token, { signal });
}

async function responseError(response: Response): Promise<FloorPlanEditorApiError> {
  let errorBody: Partial<ApiErrorBody> & { detail?: Partial<ApiErrorBody> } = {};
  try {
    errorBody = (await response.json()) as typeof errorBody;
  } catch {
    errorBody = {};
  }
  const problem = errorBody.detail ?? errorBody;
  return new FloorPlanEditorApiError(
    problem.message ?? `Editor request failed with status ${response.status}.`,
    response.status,
    problem.code ?? "EDITOR_REQUEST_FAILED",
    problem.details ?? {},
  );
}
