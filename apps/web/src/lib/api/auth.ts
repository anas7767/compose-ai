import type { AuthBootstrapRequest, AuthContextResponse } from "@compose-ai/shared";

import { apiBaseUrl } from "./config";

export class AuthApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "AuthApiError";
  }
}

async function readAuthContextResponse(
  response: Response,
  operation: string,
): Promise<AuthContextResponse> {
  if (!response.ok) {
    throw new AuthApiError(`Compose ${operation} failed with status ${response.status}.`, response.status);
  }

  const body = (await response.json()) as { data: AuthContextResponse };

  return body.data;
}

export async function bootstrapAuthenticatedUser(
  token: string,
  payload: AuthBootstrapRequest,
): Promise<AuthContextResponse> {
  const response = await fetch(`${apiBaseUrl}/auth/bootstrap`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });


  return readAuthContextResponse(response, "auth bootstrap");
}

export async function getAuthenticatedContext(
  token: string,
  signal?: AbortSignal,
): Promise<AuthContextResponse> {
  const response = await fetch(`${apiBaseUrl}/auth/me`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    cache: "no-store",
    signal,
  });

  return readAuthContextResponse(response, "account context request");
}
