"use client";

import { useAuth } from "@clerk/nextjs";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  cancelSceneJob,
  compileScene,
  createSceneCameraView,
  getSceneCameraViews,
  getSceneMaterials,
  getSceneObjects,
  getSceneWorkspace,
} from "@/lib/api/building-visualization";

async function requireSceneToken(getToken: () => Promise<string | null>): Promise<string> {
  const token = await getToken();
  if (!token) throw new Error("Missing Clerk session token.");
  return token;
}

function createIdempotencyKey(): string {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `scene-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function useSceneWorkspace(projectId: string) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  return useQuery({
    enabled: Boolean(projectId) && isLoaded && isSignedIn,
    queryFn: async ({ signal }) =>
      getSceneWorkspace(await requireSceneToken(getToken), projectId, signal),
    queryKey: ["building-visualization", projectId, "workspace"],
  });
}

export function useSceneObjects(projectId: string, sceneVersionId?: string | null) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  return useQuery({
    enabled: Boolean(projectId && sceneVersionId) && isLoaded && isSignedIn,
    queryFn: async ({ signal }) =>
      getSceneObjects(await requireSceneToken(getToken), projectId, sceneVersionId ?? "", signal),
    queryKey: ["building-visualization", projectId, sceneVersionId, "objects"],
  });
}

export function useSceneMaterials(projectId: string, sceneVersionId?: string | null) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  return useQuery({
    enabled: Boolean(projectId && sceneVersionId) && isLoaded && isSignedIn,
    queryFn: async ({ signal }) =>
      getSceneMaterials(await requireSceneToken(getToken), projectId, sceneVersionId ?? "", signal),
    queryKey: ["building-visualization", projectId, sceneVersionId, "materials"],
  });
}

export function useSceneCameraViews(projectId: string, sceneVersionId?: string | null) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  return useQuery({
    enabled: Boolean(projectId && sceneVersionId) && isLoaded && isSignedIn,
    queryFn: async ({ signal }) =>
      getSceneCameraViews(await requireSceneToken(getToken), projectId, sceneVersionId ?? "", signal),
    queryKey: ["building-visualization", projectId, sceneVersionId, "camera-views"],
  });
}

export function useSceneActions(projectId: string) {
  const { getToken } = useAuth();
  const queryClient = useQueryClient();
  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ["building-visualization", projectId] });
  };
  return {
    cancel: useMutation({
      mutationFn: async (jobId: string) =>
        cancelSceneJob(await requireSceneToken(getToken), projectId, jobId),
      onSuccess: invalidate,
    }),
    compile: useMutation({
      mutationFn: async (checkpointId?: string | null) =>
        compileScene(
          await requireSceneToken(getToken),
          projectId,
          { checkpointId: checkpointId ?? null, qualityPreset: "balanced" },
          createIdempotencyKey(),
        ),
      onSuccess: invalidate,
    }),
    createCameraView: useMutation({
      mutationFn: async (input: Parameters<typeof createSceneCameraView>[3] & { sceneVersionId: string }) =>
        createSceneCameraView(
          await requireSceneToken(getToken),
          projectId,
          input.sceneVersionId,
          { name: input.name, camera: input.camera },
        ),
      onSuccess: invalidate,
    }),
  };
}
