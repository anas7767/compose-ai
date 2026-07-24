import type {
  ApiEnvelope,
  ApiErrorBody,
  PaginationMeta,
  ProjectActivity,
  ProjectCreateRequest,
  ProjectDashboardSummary,
  ProjectDetail,
  ProjectDuplicateRequest,
  ProjectListView,
  ProjectSummary,
  ProjectType,
  ProjectUpdateRequest,
} from "@compose-ai/shared";

import { apiBaseUrl } from "./config";

export class ProjectApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ProjectApiError";
  }
}

interface ProjectListOptions {
  cursor?: string | null;
  limit?: number;
  projectType?: ProjectType | null;
  query?: string;
  tag?: string;
  view?: ProjectListView;
}

interface ProjectListResult {
  pagination: PaginationMeta;
  projects: ProjectSummary[];
}

async function projectRequest<TData>(
  path: string,
  token: string,
  init: RequestInit = {},
): Promise<{ data: TData; response: Response; meta: ApiEnvelope<TData>["meta"] }> {
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
    let errorBody: Partial<ApiErrorBody> & {
      detail?: Partial<ApiErrorBody>;
    } = {};
    try {
      errorBody = (await response.json()) as typeof errorBody;
    } catch {
      errorBody = {};
    }
    const problem = errorBody.detail ?? errorBody;
    throw new ProjectApiError(
      problem.message ?? `Project request failed with status ${response.status}.`,
      response.status,
      problem.code ?? "PROJECT_REQUEST_FAILED",
      problem.details ?? {},
    );
  }

  if (response.status === 204) {
    return { data: undefined as TData, response, meta: { requestId: "" } };
  }

  const body = (await response.json()) as ApiEnvelope<TData>;
  return { data: body.data, response, meta: body.meta };
}

export async function listProjects(
  token: string,
  options: ProjectListOptions = {},
  signal?: AbortSignal,
): Promise<ProjectListResult> {
  const parameters = new URLSearchParams({
    limit: String(options.limit ?? 20),
    view: options.view ?? "active",
  });
  if (options.cursor) parameters.set("cursor", options.cursor);
  if (options.query) parameters.set("q", options.query);
  if (options.projectType) parameters.set("type", options.projectType);
  if (options.tag) parameters.set("tag", options.tag);
  const result = await projectRequest<ProjectSummary[]>(
    `/projects?${parameters.toString()}`,
    token,
    { signal },
  );
  return {
    projects: result.data,
    pagination: result.meta.pagination ?? {
      hasMore: false,
      limit: options.limit ?? 20,
      nextCursor: null,
    },
  };
}

export async function getProject(
  token: string,
  projectId: string,
  signal?: AbortSignal,
): Promise<ProjectDetail> {
  return (await projectRequest<ProjectDetail>(`/projects/${projectId}`, token, { signal })).data;
}

export async function getProjectSummary(
  token: string,
  signal?: AbortSignal,
): Promise<ProjectDashboardSummary> {
  return (await projectRequest<ProjectDashboardSummary>("/projects/summary", token, { signal }))
    .data;
}

export async function getProjectActivity(
  token: string,
  limit = 10,
  projectId?: string,
  signal?: AbortSignal,
): Promise<ProjectActivity[]> {
  const path = projectId
    ? `/projects/${projectId}/activity?limit=${limit}`
    : `/projects/activity?limit=${limit}`;
  return (await projectRequest<ProjectActivity[]>(path, token, { signal })).data;
}

export async function createProject(
  token: string,
  request: ProjectCreateRequest,
  idempotencyKey: string,
): Promise<ProjectDetail> {
  return (
    await projectRequest<ProjectDetail>("/projects", token, {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(request),
    })
  ).data;
}

export async function updateProject(
  token: string,
  projectId: string,
  version: number,
  request: ProjectUpdateRequest,
): Promise<ProjectDetail> {
  return (
    await projectRequest<ProjectDetail>(`/projects/${projectId}`, token, {
      method: "PATCH",
      headers: { "If-Match": `"${version}"` },
      body: JSON.stringify(request),
    })
  ).data;
}

export async function completeProject(
  token: string,
  projectId: string,
  version: number,
): Promise<ProjectDetail> {
  return (
    await projectRequest<ProjectDetail>(`/projects/${projectId}/complete`, token, {
      method: "POST",
      headers: { "If-Match": `"${version}"` },
    })
  ).data;
}

export async function archiveProject(
  token: string,
  projectId: string,
  version: number,
): Promise<ProjectDetail> {
  return (
    await projectRequest<ProjectDetail>(`/projects/${projectId}/archive`, token, {
      method: "POST",
      headers: { "If-Match": `"${version}"` },
    })
  ).data;
}

export async function restoreProject(
  token: string,
  projectId: string,
  version: number,
): Promise<ProjectDetail> {
  return (
    await projectRequest<ProjectDetail>(`/projects/${projectId}/restore`, token, {
      method: "POST",
      headers: { "If-Match": `"${version}"` },
    })
  ).data;
}

export async function duplicateProject(
  token: string,
  projectId: string,
  request: ProjectDuplicateRequest,
  idempotencyKey: string,
): Promise<ProjectDetail> {
  return (
    await projectRequest<ProjectDetail>(`/projects/${projectId}/duplicate`, token, {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(request),
    })
  ).data;
}

export async function deleteProject(
  token: string,
  projectId: string,
  version: number,
): Promise<void> {
  await projectRequest<void>(`/projects/${projectId}`, token, {
    method: "DELETE",
    headers: { "If-Match": `"${version}"` },
  });
}

export async function restoreDeletedProject(
  token: string,
  projectId: string,
  version: number,
): Promise<ProjectDetail> {
  return (
    await projectRequest<ProjectDetail>(`/projects/${projectId}/restore-deleted`, token, {
      method: "POST",
      headers: { "If-Match": `"${version}"` },
    })
  ).data;
}
