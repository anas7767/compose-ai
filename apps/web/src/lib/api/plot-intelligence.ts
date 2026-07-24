import type {
  ApiEnvelope,
  ApiErrorBody,
  PaginationMeta,
  PlotAnalysis,
  PlotBoundaryInput,
  PlotBoundaryVersion,
  PlotIntelligence,
  PlotProfileUpdateRequest,
  PlotRestoreResponse,
} from "@compose-ai/shared";

import { apiBaseUrl } from "./config";

export class PlotApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "PlotApiError";
  }
}

interface BoundaryHistoryResult {
  boundaries: PlotBoundaryVersion[];
  pagination: PaginationMeta;
}

async function plotRequest<TData>(
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
  if (!response.ok) {
    let body: Partial<ApiErrorBody> & { detail?: Partial<ApiErrorBody> } = {};
    try {
      body = (await response.json()) as typeof body;
    } catch {
      body = {};
    }
    const problem = body.detail ?? body;
    throw new PlotApiError(
      problem.message ?? `Plot request failed with status ${response.status}.`,
      response.status,
      problem.code ?? "PLOT_REQUEST_FAILED",
      problem.details ?? {},
    );
  }
  return ((await response.json()) as ApiEnvelope<TData>).data;
}

async function plotRequestWithMeta<TData>(
  path: string,
  token: string,
  init: RequestInit = {},
): Promise<ApiEnvelope<TData>> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...init.headers,
    },
  });
  if (!response.ok) {
    let body: Partial<ApiErrorBody> & { detail?: Partial<ApiErrorBody> } = {};
    try {
      body = (await response.json()) as typeof body;
    } catch {
      body = {};
    }
    const problem = body.detail ?? body;
    throw new PlotApiError(
      problem.message ?? `Plot request failed with status ${response.status}.`,
      response.status,
      problem.code ?? "PLOT_REQUEST_FAILED",
      problem.details ?? {},
    );
  }
  return (await response.json()) as ApiEnvelope<TData>;
}

export function getPlotIntelligence(
  token: string,
  projectId: string,
  signal?: AbortSignal,
): Promise<PlotIntelligence> {
  return plotRequest(`/projects/${projectId}/plot`, token, { signal });
}

export function validatePlotProfile(
  token: string,
  projectId: string,
  request: PlotProfileUpdateRequest,
): Promise<PlotAnalysis> {
  return plotRequest(`/projects/${projectId}/plot/validate`, token, {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function updatePlotProfile(
  token: string,
  projectId: string,
  version: number,
  request: PlotProfileUpdateRequest,
  idempotencyKey: string,
): Promise<PlotIntelligence> {
  return plotRequest(`/projects/${projectId}/plot`, token, {
    method: "PATCH",
    headers: { "If-Match": `"${version}"`, "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(request),
  });
}

export function createPlotBoundary(
  token: string,
  projectId: string,
  version: number,
  request: PlotBoundaryInput,
  idempotencyKey: string,
): Promise<PlotIntelligence> {
  return plotRequest(`/projects/${projectId}/plot/boundary-versions`, token, {
    method: "POST",
    headers: { "If-Match": `"${version}"`, "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(request),
  });
}

export async function listPlotBoundaryHistory(
  token: string,
  projectId: string,
  options: { cursor?: string | null; limit?: number } = {},
): Promise<BoundaryHistoryResult> {
  const parameters = new URLSearchParams({ limit: String(options.limit ?? 20) });
  if (options.cursor) parameters.set("cursor", options.cursor);
  const envelope = await plotRequestWithMeta<PlotBoundaryVersion[]>(
    `/projects/${projectId}/plot/boundary-versions?${parameters.toString()}`,
    token,
  );
  return {
    boundaries: envelope.data,
    pagination: envelope.meta.pagination ?? {
      hasMore: false,
      limit: options.limit ?? 20,
      nextCursor: null,
    },
  };
}

export function restorePlotBoundary(
  token: string,
  projectId: string,
  boundaryId: string,
  version: number,
  idempotencyKey: string,
): Promise<PlotRestoreResponse> {
  return plotRequest(
    `/projects/${projectId}/plot/boundary-versions/${boundaryId}/restore`,
    token,
    {
      method: "POST",
      headers: { "If-Match": `"${version}"`, "Idempotency-Key": idempotencyKey },
    },
  );
}

export function undoPlotBoundaryRestore(
  token: string,
  projectId: string,
  actionId: string,
  version: number,
  idempotencyKey: string,
): Promise<PlotIntelligence> {
  return plotRequest(`/projects/${projectId}/plot/boundary-restores/${actionId}/undo`, token, {
    method: "POST",
    headers: { "If-Match": `"${version}"`, "Idempotency-Key": idempotencyKey },
  });
}

export function clearPlotBoundary(
  token: string,
  projectId: string,
  version: number,
  idempotencyKey: string,
): Promise<PlotIntelligence> {
  return plotRequest(`/projects/${projectId}/plot/boundary`, token, {
    method: "DELETE",
    headers: { "If-Match": `"${version}"`, "Idempotency-Key": idempotencyKey },
  });
}

export function recalculatePlotAnalysis(
  token: string,
  projectId: string,
  version: number,
  idempotencyKey: string,
): Promise<PlotIntelligence> {
  return plotRequest(`/projects/${projectId}/plot/recalculate`, token, {
    method: "POST",
    headers: { "If-Match": `"${version}"`, "Idempotency-Key": idempotencyKey },
  });
}
