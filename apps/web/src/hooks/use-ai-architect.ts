"use client";

import { useAuth } from "@clerk/nextjs";
import { useQuery } from "@tanstack/react-query";

import {
  getAIMemory,
  getAIRun,
  getAISuggestedPrompts,
  getAIUsage,
  getCurrentAIBrief,
  listAIMessages,
  listAIThreads,
} from "@/lib/api/ai-architect";

export async function requireSessionToken(
  getToken: () => Promise<string | null>,
): Promise<string> {
  const token = await getToken();
  if (!token) throw new Error("Missing Clerk session token.");
  return token;
}

export function useAIThreads(projectId: string) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  return useQuery({
    queryKey: ["ai", projectId, "threads"],
    enabled: isLoaded && isSignedIn,
    queryFn: async ({ signal }) =>
      listAIThreads(await requireSessionToken(getToken), projectId, signal),
  });
}

export function useAIMessages(projectId: string, threadId: string | null) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  return useQuery({
    queryKey: ["ai", projectId, "threads", threadId, "messages"],
    enabled: Boolean(threadId) && isLoaded && isSignedIn,
    queryFn: async ({ signal }) =>
      listAIMessages(
        await requireSessionToken(getToken),
        projectId,
        threadId as string,
        signal,
      ),
  });
}

export function useCurrentAIBrief(projectId: string) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  return useQuery({
    queryKey: ["ai", projectId, "brief", "current"],
    enabled: isLoaded && isSignedIn,
    queryFn: async ({ signal }) =>
      getCurrentAIBrief(await requireSessionToken(getToken), projectId, signal),
  });
}

export function useAIMemory(projectId: string) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  return useQuery({
    queryKey: ["ai", projectId, "memory", "current"],
    enabled: isLoaded && isSignedIn,
    queryFn: async ({ signal }) =>
      getAIMemory(await requireSessionToken(getToken), projectId, signal),
  });
}

export function useAIUsage(projectId: string) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  return useQuery({
    queryKey: ["ai", projectId, "usage"],
    enabled: isLoaded && isSignedIn,
    queryFn: async ({ signal }) =>
      getAIUsage(await requireSessionToken(getToken), projectId, signal),
  });
}

export function useAISuggestedPrompts(projectId: string) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  return useQuery({
    queryKey: ["ai", projectId, "suggested-prompts"],
    enabled: isLoaded && isSignedIn,
    staleTime: 5 * 60 * 1000,
    queryFn: async ({ signal }) =>
      getAISuggestedPrompts(await requireSessionToken(getToken), projectId, signal),
  });
}

export function useAIRun(projectId: string, runId: string | null) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  return useQuery({
    queryKey: ["ai", projectId, "runs", runId],
    enabled: Boolean(runId) && isLoaded && isSignedIn,
    queryFn: async ({ signal }) =>
      getAIRun(await requireSessionToken(getToken), projectId, runId as string, signal),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && ["completed", "failed", "cancelled"].includes(status) ? false : 1000;
    },
  });
}
