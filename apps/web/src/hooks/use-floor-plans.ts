"use client";

import { useAuth } from "@clerk/nextjs";
import { useQuery } from "@tanstack/react-query";

import {
  getFloorPlanReadiness,
  getFloorPlanRun,
  listFloorPlanDesignVersions,
  listFloorPlanOptions,
  listFloorPlanRuns,
} from "@/lib/api/floor-plans";

export async function requireFloorPlanToken(
  getToken: () => Promise<string | null>,
): Promise<string> {
  const token = await getToken();
  if (!token) throw new Error("Missing Clerk session token.");
  return token;
}

export function useFloorPlanReadiness(projectId: string) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  return useQuery({
    queryKey: ["floor-plans", projectId, "readiness"],
    enabled: Boolean(projectId) && isLoaded && isSignedIn,
    queryFn: async ({ signal }) =>
      getFloorPlanReadiness(await requireFloorPlanToken(getToken), projectId, signal),
  });
}

export function useFloorPlanRuns(projectId: string) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  return useQuery({
    queryKey: ["floor-plans", projectId, "runs"],
    enabled: Boolean(projectId) && isLoaded && isSignedIn,
    queryFn: async ({ signal }) =>
      listFloorPlanRuns(await requireFloorPlanToken(getToken), projectId, signal),
  });
}

export function useFloorPlanRun(projectId: string, runId: string | null) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  return useQuery({
    queryKey: ["floor-plans", projectId, "runs", runId],
    enabled: Boolean(projectId && runId) && isLoaded && isSignedIn,
    queryFn: async ({ signal }) =>
      getFloorPlanRun(
        await requireFloorPlanToken(getToken),
        projectId,
        runId as string,
        signal,
      ),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && !["completed", "partial", "failed", "cancelled"].includes(status)
        ? 1_500
        : false;
    },
  });
}

export function useFloorPlanOptions(projectId: string, runId: string | null) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  return useQuery({
    queryKey: ["floor-plans", projectId, "runs", runId, "options"],
    enabled: Boolean(projectId && runId) && isLoaded && isSignedIn,
    queryFn: async ({ signal }) =>
      listFloorPlanOptions(
        await requireFloorPlanToken(getToken),
        projectId,
        runId as string,
        signal,
      ),
  });
}

export function useFloorPlanDesignVersions(projectId: string) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  return useQuery({
    queryKey: ["floor-plans", projectId, "design-versions"],
    enabled: Boolean(projectId) && isLoaded && isSignedIn,
    queryFn: async ({ signal }) =>
      listFloorPlanDesignVersions(await requireFloorPlanToken(getToken), projectId, signal),
  });
}
