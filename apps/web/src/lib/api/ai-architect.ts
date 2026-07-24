import type {
  AIBrief,
  AIBriefAccepted,
  AIBriefGenerateRequest,
  AIMessage,
  AIMessageAccepted,
  AIMessageCreateRequest,
  AIMemory,
  AIProposal,
  AIProposalApplyResponse,
  AIRun,
  AIRunEvent,
  AIRunRetry,
  AISuggestedPrompt,
  AIThread,
  AIThreadCreateRequest,
  AIUsage,
  ApiEnvelope,
  ApiErrorBody,
} from "@compose-ai/shared";

import { apiBaseUrl } from "./config";

export class AIArchitectApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "AIArchitectApiError";
  }
}

async function aiRequest<TData>(
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
  const body = (await response.json()) as ApiEnvelope<TData>;
  return body.data;
}

export function listAIThreads(token: string, projectId: string, signal?: AbortSignal) {
  return aiRequest<AIThread[]>(`/projects/${projectId}/ai/threads?limit=50`, token, { signal });
}

export function createAIThread(
  token: string,
  projectId: string,
  request: AIThreadCreateRequest,
  idempotencyKey: string,
) {
  return aiRequest<AIThread>(`/projects/${projectId}/ai/threads`, token, {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(request),
  });
}

export function renameAIThread(
  token: string,
  projectId: string,
  threadId: string,
  title: string,
) {
  return aiRequest<AIThread>(`/projects/${projectId}/ai/threads/${threadId}`, token, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
}

export function archiveAIThread(
  token: string,
  projectId: string,
  threadId: string,
) {
  return aiRequest<AIThread>(`/projects/${projectId}/ai/threads/${threadId}/archive`, token, {
    method: "POST",
  });
}

export function listAIMessages(
  token: string,
  projectId: string,
  threadId: string,
  signal?: AbortSignal,
) {
  return aiRequest<AIMessage[]>(
    `/projects/${projectId}/ai/threads/${threadId}/messages?limit=100`,
    token,
    { signal },
  );
}

export function sendAIMessage(
  token: string,
  projectId: string,
  threadId: string,
  request: AIMessageCreateRequest,
  idempotencyKey: string,
) {
  return aiRequest<AIMessageAccepted>(
    `/projects/${projectId}/ai/threads/${threadId}/messages`,
    token,
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(request),
    },
  );
}

export function getAIRun(token: string, projectId: string, runId: string, signal?: AbortSignal) {
  return aiRequest<AIRun>(`/projects/${projectId}/ai/runs/${runId}`, token, { signal });
}

export function cancelAIRun(token: string, projectId: string, runId: string) {
  return aiRequest<AIRun>(`/projects/${projectId}/ai/runs/${runId}/cancel`, token, {
    method: "POST",
  });
}

export function retryAIRun(
  token: string,
  projectId: string,
  runId: string,
  idempotencyKey: string,
) {
  return aiRequest<AIRunRetry>(`/projects/${projectId}/ai/runs/${runId}/retry`, token, {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
  });
}

export async function streamAIRun(
  token: string,
  projectId: string,
  runId: string,
  onEvent: (event: AIRunEvent) => void,
  signal?: AbortSignal,
  lastEventId?: number,
): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/projects/${projectId}/ai/runs/${runId}/events`, {
    cache: "no-store",
    headers: {
      Accept: "text/event-stream",
      Authorization: `Bearer ${token}`,
      ...(lastEventId ? { "Last-Event-ID": String(lastEventId) } : {}),
    },
    signal,
  });
  if (!response.ok) throw await responseError(response);
  if (!response.body) {
    throw new AIArchitectApiError("The AI stream did not return a response body.", 502, "AI_STREAM_EMPTY");
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
      if (data) onEvent(JSON.parse(data) as AIRunEvent);
      boundary = buffer.indexOf("\n\n");
    }
    if (done) break;
  }
}

export function generateAIBrief(
  token: string,
  projectId: string,
  request: AIBriefGenerateRequest,
  idempotencyKey: string,
) {
  return aiRequest<AIBriefAccepted>(`/projects/${projectId}/ai/briefs/generate`, token, {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(request),
  });
}

export function getCurrentAIBrief(token: string, projectId: string, signal?: AbortSignal) {
  return aiRequest<AIBrief | null>(`/projects/${projectId}/ai/briefs/current`, token, { signal });
}

export function reviewAIBrief(
  token: string,
  projectId: string,
  briefId: string,
  decision: "approve" | "reject",
  idempotencyKey: string,
) {
  return aiRequest<AIBrief>(
    `/projects/${projectId}/ai/briefs/${briefId}/${decision}`,
    token,
    { method: "POST", headers: { "Idempotency-Key": idempotencyKey } },
  );
}

export function reviewAIProposal(
  token: string,
  projectId: string,
  proposalId: string,
  decision: "approve" | "reject",
  idempotencyKey: string,
) {
  return aiRequest<AIProposal>(
    `/projects/${projectId}/ai/proposals/${proposalId}/${decision}`,
    token,
    { method: "POST", headers: { "Idempotency-Key": idempotencyKey } },
  );
}

export function applyAIProposals(
  token: string,
  projectId: string,
  projectVersion: number,
  proposalIds: string[],
  idempotencyKey: string,
) {
  return aiRequest<AIProposalApplyResponse>(`/projects/${projectId}/ai/proposals/apply`, token, {
    method: "POST",
    headers: {
      "Idempotency-Key": idempotencyKey,
      "If-Match": `"${projectVersion}"`,
    },
    body: JSON.stringify({ proposalIds }),
  });
}

export function getAIMemory(token: string, projectId: string, signal?: AbortSignal) {
  return aiRequest<AIMemory | null>(`/projects/${projectId}/ai/memory/current`, token, { signal });
}

export function getAIUsage(token: string, projectId: string, signal?: AbortSignal) {
  return aiRequest<AIUsage>(`/projects/${projectId}/ai/usage`, token, { signal });
}

export function getAISuggestedPrompts(token: string, projectId: string, signal?: AbortSignal) {
  return aiRequest<AISuggestedPrompt[]>(`/projects/${projectId}/ai/suggested-prompts`, token, {
    signal,
  });
}

async function responseError(response: Response): Promise<AIArchitectApiError> {
  let errorBody: Partial<ApiErrorBody> & { detail?: Partial<ApiErrorBody> } = {};
  try {
    errorBody = (await response.json()) as typeof errorBody;
  } catch {
    errorBody = {};
  }
  const problem = errorBody.detail ?? errorBody;
  return new AIArchitectApiError(
    problem.message ?? `AI Architect request failed with status ${response.status}.`,
    response.status,
    problem.code ?? "AI_REQUEST_FAILED",
    problem.details ?? {},
  );
}
