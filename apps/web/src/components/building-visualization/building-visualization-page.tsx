"use client";

import type {
  SceneClipBox,
  SceneEnvironmentPreset,
  SceneGraphNode,
  SceneObject,
  SceneQualityPreset,
} from "@compose-ai/shared";
import {
  AlertTriangle,
  Box,
  Camera,
  CheckCircle2,
  Cuboid,
  Eye,
  EyeOff,
  Focus,
  Layers3,
  Maximize2,
  Play,
  RefreshCw,
  Scissors,
  SlidersHorizontal,
  SunMedium,
  Trees,
} from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useSceneActions,
  useSceneCameraViews,
  useSceneMaterials,
  useSceneObjects,
  useSceneWorkspace,
} from "@/hooks/use-building-visualization";
import { cn } from "@/lib/utils";

import { ThreeSceneRenderer } from "./renderer/three-scene-renderer";

interface BuildingVisualizationPageProps {
  projectId: string;
}

const objectTone: Record<string, string> = {
  door: "bg-amber-50 text-amber-700 ring-amber-200",
  floor: "bg-slate-50 text-slate-700 ring-slate-200",
  room: "bg-violet-50 text-violet-700 ring-violet-200",
  stair: "bg-blue-50 text-blue-700 ring-blue-200",
  wall: "bg-slate-100 text-slate-700 ring-slate-200",
  window: "bg-cyan-50 text-cyan-700 ring-cyan-200",
};

export function BuildingVisualizationPage({ projectId }: BuildingVisualizationPageProps) {
  const workspace = useSceneWorkspace(projectId);
  const sceneId = workspace.data?.activeScene?.id;
  const objects = useSceneObjects(projectId, sceneId);
  const materials = useSceneMaterials(projectId, sceneId);
  const cameras = useSceneCameraViews(projectId, sceneId);
  const actions = useSceneActions(projectId);
  const [selectedSourceId, setSelectedSourceId] = React.useState<string | null>(null);
  const [selectedStableId, setSelectedStableId] = React.useState<string | null>(null);
  const [cameraPresetId, setCameraPresetId] = React.useState("isometric");
  const [environmentPreset, setEnvironmentPreset] = React.useState<SceneEnvironmentPreset>("noon");
  const [qualityPreset, setQualityPreset] = React.useState<SceneQualityPreset>("balanced");
  const [roofVisible, setRoofVisible] = React.useState(true);
  const [wallOpacity, setWallOpacity] = React.useState(0.88);
  const [sectionBox, setSectionBox] = React.useState<SceneClipBox>({ enabled: false });
  const activeScene = workspace.data?.activeScene ?? null;
  const sceneObjects = objects.data?.objects ?? [];
  const sceneMaterials = materials.data?.materials ?? workspace.data?.materialLibrary ?? [];
  const selectedObject = sceneObjects.find((object) => object.stableObjectId === selectedStableId);

  React.useEffect(() => {
    if (activeScene?.manifest.cameraPresets[0]?.id) {
      setCameraPresetId(activeScene.manifest.cameraPresets[0].id);
    }
  }, [activeScene?.id, activeScene?.manifest.cameraPresets]);

  if (workspace.isLoading) return <VisualizationSkeleton />;

  if (workspace.isError) {
    return (
      <VisualizationState
        action={<Button onClick={() => workspace.refetch()}>Retry</Button>}
        icon={AlertTriangle}
        title="3D workspace could not load"
      >
        The visualization workspace could not load. Your source project data has not been changed.
      </VisualizationState>
    );
  }

  if (!workspace.data?.hasValidatedCheckpoint) {
    return (
      <VisualizationState
        action={
          <Button asChild>
            <Link href={`/projects/${projectId}/editor`}>Open 2D editor</Link>
          </Button>
        }
        icon={Cuboid}
        title="Create a validated 2D checkpoint first"
      >
        The 3D model is compiled from an immutable editor checkpoint, keeping the 2D plan as the
        source of truth.
      </VisualizationState>
    );
  }

  const compiling = actions.compile.isPending || workspace.data.latestJob?.status?.includes("ing");

  return (
    <main className="compose-visualization-light min-h-screen bg-[#f7f8fc] px-4 py-5 text-slate-950 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-[1680px] flex-col gap-5">
        <section className="rounded-[30px] border border-white/80 bg-white/85 p-5 shadow-[0_24px_80px_rgba(79,70,229,0.10)] backdrop-blur">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-violet-100 bg-violet-50 px-3 py-1 text-xs font-semibold text-violet-700">
                <Box className="size-3.5" />
                Conceptual Model - Not for Construction
              </div>
              <h1 className="mt-3 text-2xl font-semibold tracking-tight text-slate-950 sm:text-3xl">
                3D Building Visualization
              </h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
                Compile validated 2D checkpoints into a source-linked 3D scene for spatial review,
                sectioning, floor isolation, materials, lighting, and walkthrough foundations.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                disabled={actions.compile.isPending}
                onClick={() => actions.compile.mutate(workspace.data?.sourceCheckpointId)}
              >
                {activeScene ? <RefreshCw className="mr-2 size-4" /> : <Play className="mr-2 size-4" />}
                {activeScene ? "Recompile" : "Compile 3D"}
              </Button>
              <Button asChild variant="outline">
                <Link href={`/projects/${projectId}/editor`}>Open 2D source</Link>
              </Button>
            </div>
          </div>
        </section>

        <section className="grid gap-5 xl:grid-cols-[280px_minmax(0,1fr)_320px]">
          <aside className="order-2 space-y-4 xl:order-1">
            <SceneGraphPanel
              graph={objects.data?.graph ?? workspace.data.sceneGraph}
              onSelect={(sourceId, stableId) => {
                setSelectedSourceId(sourceId);
                setSelectedStableId(stableId);
              }}
              selectedStableId={selectedStableId}
            />
            <MaterialLibraryPanel materials={workspace.data.materialLibrary} />
          </aside>

          <section className="order-1 min-h-[620px] overflow-hidden rounded-[32px] border border-white/80 bg-white shadow-[0_28px_90px_rgba(15,23,42,0.10)] xl:order-2">
            <ViewerToolbar
              activeScene={activeScene}
              cameraPresetId={cameraPresetId}
              environmentPreset={environmentPreset}
              qualityPreset={qualityPreset}
              roofVisible={roofVisible}
              sectionBox={sectionBox}
              setCameraPresetId={setCameraPresetId}
              setEnvironmentPreset={setEnvironmentPreset}
              setQualityPreset={setQualityPreset}
              setRoofVisible={setRoofVisible}
              setSectionBox={setSectionBox}
              setWallOpacity={setWallOpacity}
              wallOpacity={wallOpacity}
            />
            <div className="relative h-[620px] bg-[radial-gradient(circle_at_top_left,rgba(124,58,237,0.13),transparent_35%),linear-gradient(180deg,#ffffff,#f8fafc)]">
              {activeScene && sceneObjects.length ? (
                <ThreeSceneRenderer
                  cameraPresetId={cameraPresetId}
                  cameraPresets={activeScene.manifest.cameraPresets}
                  environmentPreset={environmentPreset}
                  materials={sceneMaterials}
                  objects={sceneObjects}
                  onObjectSelect={(sourceId, stableId) => {
                    setSelectedSourceId(sourceId);
                    setSelectedStableId(stableId);
                  }}
                  qualityPreset={qualityPreset}
                  roofVisible={roofVisible}
                  sectionBox={sectionBox}
                  selectedSourceObjectId={selectedSourceId}
                  wallOpacity={wallOpacity}
                />
              ) : (
                <div className="flex h-full items-center justify-center p-8 text-center">
                  <div className="max-w-md">
                    <div className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-violet-50 text-violet-700">
                      <Cuboid className="size-7" />
                    </div>
                    <h2 className="mt-5 text-lg font-semibold text-slate-950">
                      Ready to compile your conceptual model
                    </h2>
                    <p className="mt-2 text-sm leading-6 text-slate-500">
                      The latest validated editor checkpoint is available. Compile a deterministic
                      scene version to review the building in 3D.
                    </p>
                  </div>
                </div>
              )}
              {compiling ? <CompilationOverlay progress={workspace.data.latestJob?.progress ?? 18} /> : null}
            </div>
          </section>

          <aside className="order-3 space-y-4">
            <ObjectInspector object={selectedObject} selectedSourceId={selectedSourceId} />
            <ValidationPanel
              issueCount={activeScene?.validationSummary.issueCount ?? 0}
              status={activeScene?.validationSummary.status ?? "valid"}
            />
            <CameraPanel
              cameraCount={(activeScene?.manifest.cameraPresets.length ?? 0) + (cameras.data?.views.length ?? 0)}
            />
          </aside>
        </section>
      </div>
    </main>
  );
}

function ViewerToolbar(props: {
  activeScene: NonNullable<ReturnType<typeof useSceneWorkspace>["data"]>["activeScene"] | null;
  cameraPresetId: string;
  environmentPreset: SceneEnvironmentPreset;
  qualityPreset: SceneQualityPreset;
  roofVisible: boolean;
  sectionBox: SceneClipBox;
  setCameraPresetId: (value: string) => void;
  setEnvironmentPreset: (value: SceneEnvironmentPreset) => void;
  setQualityPreset: (value: SceneQualityPreset) => void;
  setRoofVisible: (value: boolean) => void;
  setSectionBox: (value: SceneClipBox) => void;
  setWallOpacity: (value: number) => void;
  wallOpacity: number;
}) {
  const presets = props.activeScene?.manifest.cameraPresets ?? [];
  return (
    <div className="flex flex-col gap-3 border-b border-slate-100 bg-white/85 p-3 backdrop-blur lg:flex-row lg:items-center lg:justify-between">
      <div className="flex flex-wrap gap-2">
        {presets.map((preset) => (
          <button
            className={cn(
              "rounded-full px-3 py-1.5 text-xs font-semibold transition hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-300",
              props.cameraPresetId === preset.id
                ? "bg-slate-950 text-white shadow-sm"
                : "bg-white text-slate-600 ring-1 ring-slate-200",
            )}
            key={preset.id}
            onClick={() => props.setCameraPresetId(preset.id)}
            type="button"
          >
            {preset.label}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <ToolbarSelect
          icon={SunMedium}
          label="Environment"
          onChange={(value) => props.setEnvironmentPreset(value as SceneEnvironmentPreset)}
          value={props.environmentPreset}
          values={["morning", "noon", "evening", "night"]}
        />
        <ToolbarSelect
          icon={SlidersHorizontal}
          label="Quality"
          onChange={(value) => props.setQualityPreset(value as SceneQualityPreset)}
          value={props.qualityPreset}
          values={["low", "balanced", "high"]}
        />
        <button
          className="inline-flex h-9 items-center gap-2 rounded-full border border-slate-200 bg-white px-3 font-semibold text-slate-600 transition hover:bg-slate-50"
          onClick={() => props.setRoofVisible(!props.roofVisible)}
          type="button"
        >
          {props.roofVisible ? <Eye className="size-3.5" /> : <EyeOff className="size-3.5" />}
          Roof
        </button>
        <button
          className={cn(
            "inline-flex h-9 items-center gap-2 rounded-full border px-3 font-semibold transition",
            props.sectionBox.enabled
              ? "border-violet-200 bg-violet-50 text-violet-700"
              : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50",
          )}
          onClick={() => props.setSectionBox({ enabled: !props.sectionBox.enabled })}
          type="button"
        >
          <Scissors className="size-3.5" />
          Section Box
        </button>
        <label className="inline-flex h-9 items-center gap-2 rounded-full border border-slate-200 bg-white px-3 font-semibold text-slate-600">
          Walls
          <input
            aria-label="Wall transparency"
            className="w-20 accent-violet-600"
            max={1}
            min={0.2}
            onChange={(event) => props.setWallOpacity(Number(event.target.value))}
            step={0.05}
            type="range"
            value={props.wallOpacity}
          />
        </label>
        <button
          className="inline-flex size-9 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-600 transition hover:bg-slate-50"
          type="button"
        >
          <Maximize2 className="size-4" />
        </button>
      </div>
    </div>
  );
}

function ToolbarSelect(props: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  onChange: (value: string) => void;
  value: string;
  values: string[];
}) {
  const Icon = props.icon;
  return (
    <label className="inline-flex h-9 items-center gap-2 rounded-full border border-slate-200 bg-white px-3 font-semibold text-slate-600">
      <Icon className="size-3.5" />
      <span className="sr-only">{props.label}</span>
      <select
        className="bg-transparent text-xs capitalize outline-none"
        onChange={(event) => props.onChange(event.target.value)}
        value={props.value}
      >
        {props.values.map((value) => (
          <option key={value} value={value}>
            {value}
          </option>
        ))}
      </select>
    </label>
  );
}

function SceneGraphPanel(props: {
  graph: SceneGraphNode[];
  onSelect: (sourceId: string | null, stableId: string) => void;
  selectedStableId: string | null;
}) {
  return (
    <Panel icon={Layers3} title="Scene Graph">
      <div className="space-y-2">
        {props.graph.length ? (
          props.graph.map((node) => (
            <SceneGraphItem
              key={node.id}
              node={node}
              onSelect={props.onSelect}
              selectedStableId={props.selectedStableId}
            />
          ))
        ) : (
          <p className="text-sm text-slate-500">Compile a scene to inspect the graph.</p>
        )}
      </div>
    </Panel>
  );
}

function SceneGraphItem(props: {
  depth?: number;
  node: SceneGraphNode;
  onSelect: (sourceId: string | null, stableId: string) => void;
  selectedStableId: string | null;
}) {
  const active = props.selectedStableId === props.node.id;
  return (
    <div style={{ paddingLeft: `${(props.depth ?? 0) * 12}px` }}>
      <button
        className={cn(
          "flex w-full items-center justify-between rounded-xl px-2.5 py-2 text-left text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-300",
          active ? "bg-violet-50 text-violet-700" : "text-slate-600 hover:bg-slate-50",
        )}
        onClick={() => props.onSelect(props.node.source2dObjectId, props.node.id)}
        type="button"
      >
        <span>{props.node.label}</span>
        <span className={cn("rounded-full px-2 py-0.5 ring-1", objectTone[props.node.objectType] ?? "bg-slate-50 text-slate-500 ring-slate-200")}>
          {props.node.objectType}
        </span>
      </button>
      {props.node.children.map((child) => (
        <SceneGraphItem
          depth={(props.depth ?? 0) + 1}
          key={child.id}
          node={child}
          onSelect={props.onSelect}
          selectedStableId={props.selectedStableId}
        />
      ))}
    </div>
  );
}

function MaterialLibraryPanel(props: { materials: Array<{ category: string; color: string; name: string }> }) {
  return (
    <Panel icon={Trees} title="Material Library">
      <div className="grid grid-cols-2 gap-2">
        {props.materials.map((material) => (
          <div className="rounded-2xl border border-slate-100 bg-white p-2" key={material.name}>
            <div
              className="h-10 rounded-xl ring-1 ring-black/5"
              style={{ backgroundColor: material.color }}
            />
            <p className="mt-2 truncate text-xs font-semibold text-slate-700">{material.category}</p>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function ObjectInspector(props: { object?: SceneObject; selectedSourceId: string | null }) {
  return (
    <Panel icon={Focus} title="Object Inspector">
      {props.object ? (
        <div className="space-y-4">
          <div>
            <p className="text-sm font-semibold text-slate-950">{props.object.name}</p>
            <p className="mt-1 text-xs text-slate-500">{props.object.stableObjectId}</p>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <Metric label="Type" value={props.object.objectType} />
            <Metric label="Material" value={props.object.materialId.replace("mat-", "")} />
            <Metric label="2D Source" value={props.object.source2dObjectId ?? "Generated"} />
            <Metric label="Triangles" value={String(props.object.triangleCount)} />
          </div>
          <div className="rounded-2xl bg-violet-50 p-3 text-xs leading-5 text-violet-800">
            Selecting this 3D object preserves the source 2D link for the editor handoff.
          </div>
        </div>
      ) : (
        <p className="text-sm leading-6 text-slate-500">
          Select an object in the viewport or scene graph. Source link:{" "}
          <span className="font-semibold text-slate-700">{props.selectedSourceId ?? "None"}</span>
        </p>
      )}
    </Panel>
  );
}

function ValidationPanel(props: { issueCount: number; status: "valid" | "invalid" }) {
  const valid = props.status === "valid";
  return (
    <Panel icon={valid ? CheckCircle2 : AlertTriangle} title="Validation">
      <div className={cn("rounded-2xl p-4", valid ? "bg-emerald-50" : "bg-amber-50")}>
        <p className={cn("text-sm font-semibold", valid ? "text-emerald-700" : "text-amber-700")}>
          {valid ? "Scene validation passed" : "Scene needs review"}
        </p>
        <p className="mt-1 text-xs leading-5 text-slate-500">
          {props.issueCount} issue{props.issueCount === 1 ? "" : "s"} recorded. The 2D checkpoint
          remains authoritative.
        </p>
      </div>
    </Panel>
  );
}

function CameraPanel(props: { cameraCount: number }) {
  return (
    <Panel icon={Camera} title="Camera Views">
      <div className="rounded-2xl bg-slate-50 p-4 text-sm text-slate-600">
        {props.cameraCount} preset and saved views are available for scene review.
      </div>
    </Panel>
  );
}

function Panel(props: {
  children: React.ReactNode;
  icon: React.ComponentType<{ className?: string }>;
  title: string;
}) {
  const Icon = props.icon;
  return (
    <section className="rounded-[26px] border border-white/80 bg-white/90 p-4 shadow-[0_18px_60px_rgba(15,23,42,0.07)] backdrop-blur">
      <div className="mb-4 flex items-center gap-2">
        <span className="flex size-8 items-center justify-center rounded-xl bg-slate-50 text-slate-700">
          <Icon className="size-4" />
        </span>
        <h2 className="text-sm font-semibold text-slate-950">{props.title}</h2>
      </div>
      {props.children}
    </section>
  );
}

function Metric(props: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-slate-50 p-3">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{props.label}</p>
      <p className="mt-1 truncate font-semibold text-slate-700">{props.value}</p>
    </div>
  );
}

function CompilationOverlay(props: { progress: number }) {
  return (
    <div className="absolute inset-x-6 top-6 rounded-3xl border border-white/80 bg-white/85 p-4 shadow-[0_20px_70px_rgba(79,70,229,0.16)] backdrop-blur">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-slate-950">Compiling deterministic 3D scene</p>
          <p className="mt-1 text-xs text-slate-500">Validating source geometry and saving an immutable scene version.</p>
        </div>
        <span className="text-sm font-semibold text-violet-700">{props.progress}%</span>
      </div>
      <div className="mt-3 h-2 rounded-full bg-slate-100">
        <div
          className="h-full rounded-full bg-gradient-to-r from-violet-500 to-blue-500 transition-all"
          style={{ width: `${Math.max(8, props.progress)}%` }}
        />
      </div>
    </div>
  );
}

function VisualizationSkeleton() {
  return (
    <div className="min-h-screen bg-[#f7f8fc] p-6">
      <div className="mx-auto grid max-w-[1680px] gap-5 xl:grid-cols-[280px_minmax(0,1fr)_320px]">
        <Skeleton className="h-[560px] rounded-[28px]" />
        <Skeleton className="h-[720px] rounded-[32px]" />
        <Skeleton className="h-[560px] rounded-[28px]" />
      </div>
    </div>
  );
}

function VisualizationState(props: {
  action: React.ReactNode;
  children: React.ReactNode;
  icon: React.ComponentType<{ className?: string }>;
  title: string;
}) {
  const Icon = props.icon;
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#f7f8fc] p-6">
      <section className="max-w-xl rounded-[32px] border border-white/80 bg-white/90 p-8 text-center shadow-[0_24px_80px_rgba(79,70,229,0.10)]">
        <div className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-violet-50 text-violet-700">
          <Icon className="size-7" />
        </div>
        <h1 className="mt-5 text-xl font-semibold text-slate-950">{props.title}</h1>
        <p className="mt-3 text-sm leading-6 text-slate-500">{props.children}</p>
        <div className="mt-6">{props.action}</div>
      </section>
    </main>
  );
}
