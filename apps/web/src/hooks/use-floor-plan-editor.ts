"use client";

import { useAuth } from "@clerk/nextjs";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  applyEditorOperations,
  createEditorCheckpoint,
  getEditorDocument,
  getEditorHistory,
  restoreEditorCheckpoint,
  validateEditorDocument,
} from "@/lib/api/floor-plan-editor";

async function requireEditorToken(getToken: () => Promise<string | null>): Promise<string> {
  const token = await getToken();
  if (!token) throw new Error("Missing Clerk session token.");
  return token;
}

export function useEditorDocument(projectId: string) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  return useQuery({
    enabled: Boolean(projectId) && isLoaded && isSignedIn,
    queryFn: async ({ signal }) =>
      getEditorDocument(await requireEditorToken(getToken), projectId, signal),
    queryKey: ["floor-plan-editor", projectId, "document"],
  });
}

export function useEditorHistory(projectId: string) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  return useQuery({
    enabled: Boolean(projectId) && isLoaded && isSignedIn,
    queryFn: async ({ signal }) => getEditorHistory(await requireEditorToken(getToken), projectId, signal),
    queryKey: ["floor-plan-editor", projectId, "history"],
  });
}

export function useEditorActions(projectId: string) {
  const { getToken } = useAuth();
  const queryClient = useQueryClient();
  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ["floor-plan-editor", projectId] });
  };
  return {
    applyOperations: useMutation({
      mutationFn: async (input: Parameters<typeof applyEditorOperations>[2]) =>
        applyEditorOperations(await requireEditorToken(getToken), projectId, input, crypto.randomUUID()),
      onSuccess: invalidate,
    }),
    createCheckpoint: useMutation({
      mutationFn: async (name: string) =>
        createEditorCheckpoint(await requireEditorToken(getToken), projectId, name),
      onSuccess: invalidate,
    }),
    restoreCheckpoint: useMutation({
      mutationFn: async (checkpointId: string) =>
        restoreEditorCheckpoint(await requireEditorToken(getToken), projectId, checkpointId),
      onSuccess: invalidate,
    }),
    validate: useMutation({
      mutationFn: async () => validateEditorDocument(await requireEditorToken(getToken), projectId),
      onSuccess: invalidate,
    }),
  };
}
