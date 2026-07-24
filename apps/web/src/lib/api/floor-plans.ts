import type {
  ApiEnvelope,
  ApiErrorBody,
  FloorPlanComparison,
  FloorPlanDesignVersion,
  FloorPlanGenerationAccepted,
  FloorPlanGenerationRequest,
  FloorPlanOption,
  FloorPlanReadiness,
  FloorPlanRun,
  FloorPlanRunEvent,
  FloorPlanValidation,
} from "@compose-ai/shared";

import { apiBaseUrl } from "./config";

export class FloorPlanApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "FloorPlanApiError";
  }
}

async function floorPlanRequest<TData>(
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
  if (response.status === 204) return undefined as TData;
  return ((await response.json()) as ApiEnvelope<TData>).data;
}

export function getFloorPlanReadiness(token: string, projectId: string, signal?: AbortSignal) {
  return floorPlanRequest<FloorPlanReadiness>(
    `/projects/${projectId}/floor-plans/readiness`,
    token,
    { signal },
  );
}

export function listFloorPlanRuns(token: string, projectId: string, signal?: AbortSignal) {
  return floorPlanRequest<FloorPlanRun[]>(
    `/projects/${projectId}/floor-plans/generations?limit=20`,
    token,
    { signal },
  );
}

export function getFloorPlanRun(
  token: string,
  projectId: string,
  runId: string,
  signal?: AbortSignal,
) {
  return floorPlanRequest<FloorPlanRun>(
    `/projects/${projectId}/floor-plans/generations/${runId}`,
    token,
    { signal },
  );
}

export function createFloorPlanRun(
  token: string,
  projectId: string,
  request: FloorPlanGenerationRequest,
  idempotencyKey: string,
) {
  return floorPlanRequest<FloorPlanGenerationAccepted>(
    `/projects/${projectId}/floor-plans/generations`,
    token,
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(request),
    },
  );
}

export function retryFloorPlanRun(
  token: string,
  projectId: string,
  runId: string,
  idempotencyKey: string,
) {
  return floorPlanRequest<FloorPlanGenerationAccepted>(
    `/projects/${projectId}/floor-plans/generations/${runId}/retry`,
    token,
    { method: "POST", headers: { "Idempotency-Key": idempotencyKey } },
  );
}

export function cancelFloorPlanRun(token: string, projectId: string, runId: string) {
  return floorPlanRequest<FloorPlanRun>(
    `/projects/${projectId}/floor-plans/generations/${runId}/cancel`,
    token,
    { method: "POST" },
  );
}

export function listFloorPlanOptions(
  token: string,
  projectId: string,
  runId: string,
  signal?: AbortSignal,
) {
  return floorPlanRequest<FloorPlanOption[]>(
    `/projects/${projectId}/floor-plans/generations/${runId}/options`,
    token,
    { signal },
  );
}

export function compareFloorPlanOptions(
  token: string,
  projectId: string,
  optionIds: string[],
) {
  return floorPlanRequest<FloorPlanComparison>(
    `/projects/${projectId}/floor-plans/options/compare`,
    token,
    { method: "POST", body: JSON.stringify({ optionIds }) },
  );
}

export function acceptFloorPlanOption(
  token: string,
  projectId: string,
  option: FloorPlanOption,
  name?: string,
) {
  return floorPlanRequest<FloorPlanDesignVersion>(
    `/projects/${projectId}/floor-plans/options/${option.id}/accept`,
    token,
    {
      method: "POST",
      headers: {
        "Idempotency-Key": crypto.randomUUID(),
        "If-Match": `"${option.version}"`,
      },
      body: JSON.stringify({
        confirmation: "conceptual_design_reviewed",
        name: name || null,
      }),
    },
  );
}

export function validateFloorPlanOption(token: string, projectId: string, optionId: string) {
  return floorPlanRequest<FloorPlanValidation>(
    `/projects/${projectId}/floor-plans/options/${optionId}/validate`,
    token,
    { method: "POST" },
  );
}

export function rejectFloorPlanOption(
  token: string,
  projectId: string,
  option: FloorPlanOption,
  reason: string,
) {
  return floorPlanRequest<FloorPlanOption>(
    `/projects/${projectId}/floor-plans/options/${option.id}/reject`,
    token,
    {
      method: "POST",
      headers: {
        "Idempotency-Key": crypto.randomUUID(),
        "If-Match": `"${option.version}"`,
      },
      body: JSON.stringify({ reason }),
    },
  );
}

export function listFloorPlanDesignVersions(
  token: string,
  projectId: string,
  signal?: AbortSignal,
) {
  return floorPlanRequest<FloorPlanDesignVersion[]>(
    `/projects/${projectId}/floor-plans/design-versions`,
    token,
    { signal },
  );
}

export function getFloorPlanDesignVersion(
  token: string,
  projectId: string,
  designVersionId: string,
  signal?: AbortSignal,
) {
  return floorPlanRequest<FloorPlanDesignVersion>(
    `/projects/${projectId}/floor-plans/design-versions/${designVersionId}`,
    token,
    { signal },
  );
}

export function restoreFloorPlanDesignVersion(
  token: string,
  projectId: string,
  designVersionId: string,
  name?: string,
) {
  return floorPlanRequest<FloorPlanDesignVersion>(
    `/projects/${projectId}/floor-plans/design-versions/${designVersionId}/restore`,
    token,
    {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ name: name || null }),
    },
  );
}

export function deleteFloorPlanDesignVersion(
  token: string,
  projectId: string,
  designVersionId: string,
) {
  return floorPlanRequest<void>(
    `/projects/${projectId}/floor-plans/design-versions/${designVersionId}`,
    token,
    { method: "DELETE" },
  );
}

export async function streamFloorPlanRun(
  token: string,
  projectId: string,
  runId: string,
  onEvent: (event: FloorPlanRunEvent) => void,
  signal?: AbortSignal,
  lastEventId?: number,
): Promise<void> {
  const response = await fetch(
    `${apiBaseUrl}/projects/${projectId}/floor-plans/generations/${runId}/events`,
    {
      cache: "no-store",
      headers: {
        Accept: "text/event-stream",
        Authorization: `Bearer ${token}`,
        ...(lastEventId ? { "Last-Event-ID": String(lastEventId) } : {}),
      },
      signal,
    },
  );
  if (!response.ok) throw await responseError(response);
  if (!response.body) {
    throw new FloorPlanApiError(
      "The generation stream did not return a response body.",
      502,
      "FLOOR_PLAN_STREAM_EMPTY",
    );
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done }).replaceAll("\r\n", "\n");
    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n");
      if (data) onEvent(JSON.parse(data) as FloorPlanRunEvent);
      boundary = buffer.indexOf("\n\n");
    }
    if (done) break;
  }
}

async function responseError(response: Response): Promise<FloorPlanApiError> {
  let errorBody: Partial<ApiErrorBody> & { detail?: Partial<ApiErrorBody> } = {};
  try {
    errorBody = (await response.json()) as typeof errorBody;
  } catch {
    errorBody = {};
  }
  const problem = errorBody.detail ?? errorBody;
  return new FloorPlanApiError(
    problem.message ?? `Floor-plan request failed with status ${response.status}.`,
    response.status,
    problem.code ?? "FLOOR_PLAN_REQUEST_FAILED",
    problem.details ?? {},
  );
}
