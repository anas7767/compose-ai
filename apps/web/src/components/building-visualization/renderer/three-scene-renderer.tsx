"use client";

import type { SceneBoundingBox } from "@compose-ai/shared";
import { Environment, Html, OrbitControls, PerspectiveCamera } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import * as React from "react";

import type { SceneRendererShellProps } from "./scene-renderer-types";

const unitScale = 0.001;

export function ThreeSceneRenderer(props: SceneRendererShellProps) {
  const [hasWebGl, setHasWebGl] = React.useState<boolean | null>(null);

  React.useEffect(() => {
    const canvas = document.createElement("canvas");
    const context =
      canvas.getContext("webgl2") ??
      canvas.getContext("webgl") ??
      canvas.getContext("experimental-webgl");
    setHasWebGl(Boolean(context));
  }, []);

  if (hasWebGl === false) {
    return (
      <div className="flex h-full min-h-[420px] items-center justify-center rounded-[28px] border border-slate-200 bg-white/80 p-8 text-center shadow-[0_24px_80px_rgba(79,70,229,0.10)]">
        <div className="max-w-sm">
          <p className="text-sm font-semibold text-slate-950">3D preview is unavailable</p>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            This device or browser does not expose WebGL. The scene data is preserved, and the
            viewer will load on a WebGL-capable browser.
          </p>
        </div>
      </div>
    );
  }

  if (hasWebGl === null) {
    return (
      <div className="h-full min-h-[420px] animate-pulse rounded-[28px] border border-slate-200 bg-slate-100" />
    );
  }

  const activePreset = props.cameraPresets.find((preset) => preset.id === props.cameraPresetId);
  const camera = activePreset?.camera ?? props.cameraPresets[0]?.camera;

  return (
    <Canvas
      className="compose-visualization-canvas"
      dpr={props.qualityPreset === "high" ? [1, 2] : [1, 1.5]}
      shadows={props.qualityPreset !== "low"}
    >
      {camera ? (
        <PerspectiveCamera
          fov={camera.fov}
          makeDefault
          position={toVector(camera.position)}
        />
      ) : null}
      <color args={[environmentBackground(props.environmentPreset)]} attach="background" />
      <ambientLight intensity={ambientIntensity(props.environmentPreset)} />
      <directionalLight
        castShadow={props.qualityPreset !== "low"}
        intensity={sunIntensity(props.environmentPreset)}
        position={sunPosition(props.environmentPreset)}
      />
      <Environment preset={environmentPreset(props.environmentPreset)} />
      <SceneMeshes {...props} />
      <OrbitControls
        enableDamping
        makeDefault
        maxDistance={90}
        minDistance={3}
        target={camera ? toVector(camera.target) : [0, 0, 0]}
      />
      <Html position={[0, 0.1, 0]}>
        <span className="rounded-full border border-white/70 bg-white/80 px-3 py-1 text-[11px] font-semibold text-slate-600 shadow-sm backdrop-blur">
          Conceptual Model - Not for Construction
        </span>
      </Html>
    </Canvas>
  );
}

function SceneMeshes(props: SceneRendererShellProps) {
  const materialById = new Map(props.materials.map((material) => [material.materialId, material]));
  return (
    <group>
      {props.objects
        .filter((object) => props.roofVisible || object.objectType !== "roof")
        .filter((object) => isInsideSectionBox(object.boundingBox, props.sectionBox))
        .map((object) => {
          const material = materialById.get(object.materialId);
          const selected = object.source2dObjectId === props.selectedSourceObjectId;
          const color = selected ? "#7c3aed" : material?.color ?? "#e2e8f0";
          const opacity =
            object.objectType === "wall"
              ? props.wallOpacity
              : material?.opacity ?? (object.objectType === "room" ? 0.18 : 1);
          return (
            <mesh
              castShadow
              key={object.stableObjectId}
              onClick={(event) => {
                event.stopPropagation();
                props.onObjectSelect(object.source2dObjectId, object.stableObjectId);
              }}
              position={centerOf(object.boundingBox)}
              receiveShadow
              scale={sizeOf(object.boundingBox)}
            >
              {object.objectType === "plot_boundary" ? (
                <planeGeometry args={[1, 1]} />
              ) : (
                <boxGeometry args={[1, 1, 1]} />
              )}
              <meshStandardMaterial
                color={color}
                metalness={material?.metalness ?? 0}
                opacity={opacity}
                roughness={material?.roughness ?? 0.74}
                transparent={opacity < 1 || material?.transparent || object.objectType === "room"}
                wireframe={object.objectType === "room"}
              />
            </mesh>
          );
        })}
    </group>
  );
}

function centerOf(bounds: SceneBoundingBox): [number, number, number] {
  return [
    ((bounds.min.x + bounds.max.x) / 2) * unitScale,
    ((bounds.min.y + bounds.max.y) / 2) * unitScale,
    ((bounds.min.z + bounds.max.z) / 2) * unitScale,
  ];
}

function sizeOf(bounds: SceneBoundingBox): [number, number, number] {
  return [
    Math.max((bounds.max.x - bounds.min.x) * unitScale, 0.04),
    Math.max((bounds.max.y - bounds.min.y) * unitScale, 0.04),
    Math.max((bounds.max.z - bounds.min.z) * unitScale, 0.04),
  ];
}

function toVector(value: { x: number; y: number; z: number }): [number, number, number] {
  return [value.x * unitScale, value.y * unitScale, value.z * unitScale];
}

function isInsideSectionBox(bounds: SceneBoundingBox, sectionBox: SceneRendererShellProps["sectionBox"]) {
  if (!sectionBox.enabled) return true;
  if (sectionBox.minX != null && bounds.max.x < sectionBox.minX) return false;
  if (sectionBox.maxX != null && bounds.min.x > sectionBox.maxX) return false;
  if (sectionBox.minY != null && bounds.max.y < sectionBox.minY) return false;
  if (sectionBox.maxY != null && bounds.min.y > sectionBox.maxY) return false;
  if (sectionBox.minZ != null && bounds.max.z < sectionBox.minZ) return false;
  if (sectionBox.maxZ != null && bounds.min.z > sectionBox.maxZ) return false;
  return true;
}

function environmentPreset(preset: SceneRendererShellProps["environmentPreset"]) {
  if (preset === "night") return "night";
  if (preset === "evening") return "sunset";
  if (preset === "morning") return "dawn";
  return "city";
}

function environmentBackground(preset: SceneRendererShellProps["environmentPreset"]) {
  return {
    evening: "#fff7ed",
    morning: "#f8fbff",
    night: "#eef2ff",
    noon: "#ffffff",
  }[preset];
}

function ambientIntensity(preset: SceneRendererShellProps["environmentPreset"]) {
  return { evening: 1.05, morning: 1.2, night: 0.65, noon: 1.35 }[preset];
}

function sunIntensity(preset: SceneRendererShellProps["environmentPreset"]) {
  return { evening: 2.0, morning: 2.4, night: 0.8, noon: 3.0 }[preset];
}

function sunPosition(preset: SceneRendererShellProps["environmentPreset"]): [number, number, number] {
  return {
    evening: [7, 4, 2],
    morning: [-6, 8, 4],
    night: [-3, 5, -7],
    noon: [-2, 10, 2],
  }[preset] as [number, number, number];
}
