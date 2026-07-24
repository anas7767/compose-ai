"use client";

import { useAuth } from "@clerk/nextjs";
import type { ExteriorGenerationRequest } from "@compose-ai/shared";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createExteriorGeneration,
  getExteriorOptions,
  getExteriorReadiness,
  getExteriorRuns,
} from "@/lib/api/exterior-design";

async function requireExteriorToken(getToken: () => Promise<string | null>): Promise<string> {
  const token = await getToken();
  if (!token) throw new Error("Missing Clerk session token.");
  return token;
}

function createIdempotencyKey(): string {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `exterior-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function useExteriorReadiness(projectId: string) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  return useQuery({
    enabled: Boolean(projectId) && isLoaded && isSignedIn,
    queryFn: async ({ signal }) =>
      getExteriorReadiness(await requireExteriorToken(getToken), projectId, signal),
    queryKey: ["exterior-design", projectId, "readiness"],
  });
}

export function useExteriorRuns(projectId: string) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  return useQuery({
    enabled: Boolean(projectId) && isLoaded && isSignedIn,
    queryFn: async ({ signal }) =>
      getExteriorRuns(await requireExteriorToken(getToken), projectId, signal),
    queryKey: ["exterior-design", projectId, "runs"],
  });
}

export function useExteriorOptions(projectId: string) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  return useQuery({
    enabled: Boolean(projectId) && isLoaded && isSignedIn,
    queryFn: async ({ signal }) =>
      getExteriorOptions(await requireExteriorToken(getToken), projectId, signal),
    queryKey: ["exterior-design", projectId, "options"],
  });
}

export function useExteriorActions(projectId: string) {
  const { getToken } = useAuth();
  const queryClient = useQueryClient();
  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ["exterior-design", projectId] });
  };
  return {
    generate: useMutation({
      mutationFn: async (request: ExteriorGenerationRequest) =>
        createExteriorGeneration(
          await requireExteriorToken(getToken),
          projectId,
          request,
          createIdempotencyKey(),
        ),
      onSuccess: invalidate,
    }),
  };
}
