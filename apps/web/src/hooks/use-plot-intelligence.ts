"use client";

import { useAuth } from "@clerk/nextjs";
import { useQuery } from "@tanstack/react-query";

import { getPlotIntelligence, listPlotBoundaryHistory } from "@/lib/api/plot-intelligence";

async function requireToken(getToken: () => Promise<string | null>): Promise<string> {
  const token = await getToken();
  if (!token) throw new Error("Missing Clerk session token.");
  return token;
}

export function usePlotIntelligence(projectId: string | null) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  return useQuery({
    queryKey: ["plots", "detail", projectId],
    enabled: Boolean(projectId) && isLoaded && isSignedIn,
    queryFn: async ({ signal }) =>
      getPlotIntelligence(await requireToken(getToken), projectId as string, signal),
  });
}

export function usePlotBoundaryHistory(projectId: string | null, limit = 20) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  return useQuery({
    queryKey: ["plots", "boundaries", projectId, limit],
    enabled: Boolean(projectId) && isLoaded && isSignedIn,
    queryFn: async () =>
      listPlotBoundaryHistory(await requireToken(getToken), projectId as string, { limit }),
  });
}
