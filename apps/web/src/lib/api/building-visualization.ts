import type {
  ApiEnvelope,
  ApiErrorBody,
  SceneCameraView,
  SceneCameraViewsResponse,
  SceneCompilationJob,
  SceneCompileRequest,
  SceneMaterialsResponse,
  SceneObjectsResponse,
  SceneValidationIssue,
  SceneVersion,
  SceneWorkspace,
} from "@compose-ai/shared";

import { apiBaseUrl } from "./config";

export class BuildingVisualizationApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "BuildingVisualizationApiError";
  }
}

async function sceneRequest<TData>(
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

export function getSceneWorkspace(token: string, projectId: string, signal?: AbortSignal) {
  return sceneRequest<SceneWorkspace>(`/projects/${projectId}/visualization`, token, { signal });
}

export function compileScene(
  token: string,
  projectId: string,
  request: SceneCompileRequest,
  idempotencyKey: string,
) {
  return sceneRequest<SceneCompilationJob>(`/projects/${projectId}/visualization/compile`, token, {
    body: JSON.stringify(request),
    headers: { "Idempotency-Key": idempotencyKey },
    method: "POST",
  });
}

export function getSceneJob(token: string, projectId: string, jobId: string, signal?: AbortSignal) {
  return sceneRequest<SceneCompilationJob>(`/projects/${projectId}/visualization/jobs/${jobId}`, token, {
    signal,
  });
}

export function cancelSceneJob(token: string, projectId: string, jobId: string) {
  return sceneRequest<SceneCompilationJob>(
    `/projects/${projectId}/visualization/jobs/${jobId}/cancel`,
    token,
    { method: "POST" },
  );
}

export function getSceneVersions(token: string, projectId: string, signal?: AbortSignal) {
  return sceneRequest<SceneVersion[]>(`/projects/${projectId}/visualization/versions`, token, {
    signal,
  });
}

export function getSceneObjects(
  token: string,
  projectId: string,
  sceneVersionId: string,
  signal?: AbortSignal,
) {
  return sceneRequest<SceneObjectsResponse>(
    `/projects/${projectId}/visualization/versions/${sceneVersionId}/objects`,
    token,
    { signal },
  );
}

export function getSceneMaterials(
  token: string,
  projectId: string,
  sceneVersionId: string,
  signal?: AbortSignal,
) {
  return sceneRequest<SceneMaterialsResponse>(
    `/projects/${projectId}/visualization/versions/${sceneVersionId}/materials`,
    token,
    { signal },
  );
}

export function getSceneValidation(
  token: string,
  projectId: string,
  sceneVersionId: string,
  signal?: AbortSignal,
) {
  return sceneRequest<{ issues: SceneValidationIssue[] }>(
    `/projects/${projectId}/visualization/versions/${sceneVersionId}/validation`,
    token,
    { signal },
  );
}

export function getSceneCameraViews(
  token: string,
  projectId: string,
  sceneVersionId: string,
  signal?: AbortSignal,
) {
  return sceneRequest<SceneCameraViewsResponse>(
    `/projects/${projectId}/visualization/versions/${sceneVersionId}/camera-views`,
    token,
    { signal },
  );
}

export function createSceneCameraView(
  token: string,
  projectId: string,
  sceneVersionId: string,
  view: Pick<SceneCameraView, "name" | "camera">,
) {
  return sceneRequest<SceneCameraView>(
    `/projects/${projectId}/visualization/versions/${sceneVersionId}/camera-views`,
    token,
    {
      body: JSON.stringify(view),
      method: "POST",
    },
  );
}

async function responseError(response: Response): Promise<BuildingVisualizationApiError> {
  let errorBody: Partial<ApiErrorBody> & { detail?: Partial<ApiErrorBody> } = {};
  try {
    errorBody = (await response.json()) as typeof errorBody;
  } catch {
    errorBody = {};
  }
  const problem = errorBody.detail ?? errorBody;
  return new BuildingVisualizationApiError(
    problem.message ?? `3D visualization request failed with status ${response.status}.`,
    response.status,
    problem.code ?? "BUILDING_VISUALIZATION_REQUEST_FAILED",
    problem.details ?? {},
  );
}
