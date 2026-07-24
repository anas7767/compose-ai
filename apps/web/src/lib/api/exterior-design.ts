import type {
  ApiEnvelope,
  ApiErrorBody,
  ExteriorGenerationAccepted,
  ExteriorGenerationRequest,
  ExteriorOption,
  ExteriorReadiness,
  ExteriorRun,
  ExteriorRunDetail,
} from "@compose-ai/shared";

import { apiBaseUrl } from "./config";

export class ExteriorDesignApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ExteriorDesignApiError";
  }
}

async function exteriorRequest<TData>(
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

export function getExteriorReadiness(token: string, projectId: string, signal?: AbortSignal) {
  return exteriorRequest<ExteriorReadiness>(`/projects/${projectId}/exterior-design/readiness`, token, {
    signal,
  });
}

export function createExteriorGeneration(
  token: string,
  projectId: string,
  request: ExteriorGenerationRequest,
  idempotencyKey: string,
) {
  return exteriorRequest<ExteriorGenerationAccepted>(`/projects/${projectId}/exterior-design/generations`, token, {
    body: JSON.stringify(request),
    headers: { "Idempotency-Key": idempotencyKey },
    method: "POST",
  });
}

export function getExteriorRuns(token: string, projectId: string, signal?: AbortSignal) {
  return exteriorRequest<ExteriorRun[]>(`/projects/${projectId}/exterior-design/generations`, token, {
    signal,
  });
}

export function getExteriorRun(token: string, projectId: string, runId: string, signal?: AbortSignal) {
  return exteriorRequest<ExteriorRunDetail>(
    `/projects/${projectId}/exterior-design/generations/${runId}`,
    token,
    { signal },
  );
}

export function getExteriorOptions(token: string, projectId: string, signal?: AbortSignal) {
  return exteriorRequest<ExteriorOption[]>(`/projects/${projectId}/exterior-design/options`, token, {
    signal,
  });
}

async function responseError(response: Response): Promise<ExteriorDesignApiError> {
  let errorBody: Partial<ApiErrorBody> & { detail?: Partial<ApiErrorBody> } = {};
  try {
    errorBody = (await response.json()) as typeof errorBody;
  } catch {
    errorBody = {};
  }
  const problem = errorBody.detail ?? errorBody;
  return new ExteriorDesignApiError(
    problem.message ?? `Exterior design request failed with status ${response.status}.`,
    response.status,
    problem.code ?? "EXTERIOR_DESIGN_REQUEST_FAILED",
    problem.details ?? {},
  );
}
