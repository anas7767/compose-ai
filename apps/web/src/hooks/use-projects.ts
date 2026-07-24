"use client";

import { useAuth } from "@clerk/nextjs";
import type { ProjectListView, ProjectType } from "@compose-ai/shared";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";

import {
  getProject,
  getProjectActivity,
  getProjectSummary,
  listProjects,
} from "@/lib/api/projects";

async function requireToken(getToken: () => Promise<string | null>): Promise<string> {
  const token = await getToken();
  if (!token) throw new Error("Missing Clerk session token.");
  return token;
}

export function useProjectList(
  view: ProjectListView,
  query = "",
  projectType: ProjectType | null = null,
  limit = 20,
) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  return useQuery({
    queryKey: ["projects", "list", view, query, projectType, limit],
    enabled: isLoaded && isSignedIn,
    queryFn: async ({ signal }) =>
      listProjects(await requireToken(getToken), { limit, projectType, query, view }, signal),
  });
}

export function useInfiniteProjectList(
  view: ProjectListView,
  query = "",
  projectType: ProjectType | null = null,
  limit = 20,
) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  return useInfiniteQuery({
    queryKey: ["projects", "list", view, query, projectType, limit],
    enabled: isLoaded && isSignedIn,
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam, signal }) =>
      listProjects(
        await requireToken(getToken),
        { cursor: pageParam, limit, projectType, query, view },
        signal,
      ),
    getNextPageParam: (lastPage) =>
      lastPage.pagination.hasMore ? (lastPage.pagination.nextCursor ?? undefined) : undefined,
  });
}

export function useProjectDetail(projectId: string | null) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  return useQuery({
    queryKey: ["projects", "detail", projectId],
    enabled: Boolean(projectId) && isLoaded && isSignedIn,
    queryFn: async ({ signal }) =>
      getProject(await requireToken(getToken), projectId as string, signal),
  });
}

export function useProjectSummary() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  return useQuery({
    queryKey: ["projects", "summary"],
    enabled: isLoaded && isSignedIn,
    queryFn: async ({ signal }) => getProjectSummary(await requireToken(getToken), signal),
  });
}

export function useProjectActivity(limit = 10, projectId?: string) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  return useQuery({
    queryKey: ["projects", "activity", projectId ?? "all", limit],
    enabled: isLoaded && isSignedIn,
    queryFn: async ({ signal }) =>
      getProjectActivity(await requireToken(getToken), limit, projectId, signal),
  });
}
