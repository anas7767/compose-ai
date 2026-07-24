"use client";

import type {
  EditorDocument,
  EditorFloor,
  EditorInspectorTab,
  EditorObject,
  EditorOperation,
  EditorPoint,
  EditorSnapshot,
  EditorToolDefinition,
  EditorToolId,
  EditorValidationIssue,
} from "@compose-ai/shared";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  DoorOpen,
  DraftingCompass,
  Eye,
  EyeOff,
  Focus,
  Grid3X3,
  History,
  Layers3,
  MousePointer2,
  Move,
  PanelRight,
  Redo2,
  Ruler,
  Save,
  Square,
  Undo2,
  Waypoints,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useEditorActions, useEditorDocument, useEditorHistory } from "@/hooks/use-floor-plan-editor";
import { cn } from "@/lib/utils";

interface FloorPlanEditorPageProps {
  projectId: string;
}

type RendererKind = "svg";
type DragState =
  | { mode: "draw-wall"; start: EditorPoint; current: EditorPoint }
  | { mode: "draw-room"; start: EditorPoint; current: EditorPoint }
  | { mode: "move"; objectId: string; start: EditorPoint; original: EditorPoint[] }
  | null;

const toolIcons: Record<EditorToolId, React.ComponentType<{ className?: string }>> = {
  dimension: Ruler,
  door: DoorOpen,
  label: DraftingCompass,
  pan: Move,
  room: Square,
  select: MousePointer2,
  stair: Move,
  wall: Waypoints,
  window: PanelRight,
};

export function FloorPlanEditorPage({ projectId }: FloorPlanEditorPageProps) {
  const editor = useEditorDocument(projectId);
  const history = useEditorHistory(projectId);
  const actions = useEditorActions(projectId);
  const [snapshot, setSnapshot] = React.useState<EditorSnapshot | null>(null);
  const [revision, setRevision] = React.useState(0);
  const [activeTool, setActiveTool] = React.useState<EditorToolId>("select");
  const [activeFloorId, setActiveFloorId] = React.useState<string | null>(null);
  const [selectedIds, setSelectedIds] = React.useState<string[]>([]);
  const [zoom, setZoom] = React.useState(1);
  const [drag, setDrag] = React.useState<DragState>(null);
  const [measurement, setMeasurement] = React.useState<string>("Ready");
  const [inspectorTab, setInspectorTab] = React.useState<EditorInspectorTab>("properties");
  const [undoStack, setUndoStack] = React.useState<EditorSnapshot[]>([]);
  const [redoStack, setRedoStack] = React.useState<EditorSnapshot[]>([]);
  const [saveState, setSaveState] = React.useState<"saved" | "saving" | "local" | "conflict" | "error">("saved");
  const renderer: RendererKind = "svg";

  React.useEffect(() => {
    if (!editor.data) return;
    setSnapshot(editor.data.snapshot);
    setRevision(editor.data.currentRevision);
    setActiveFloorId(editor.data.viewState.activeFloorId ?? editor.data.snapshot.floors[0]?.id ?? null);
    setActiveTool(editor.data.viewState.activeTool);
    setSelectedIds(editor.data.viewState.selectedObjectIds);
  }, [editor.data]);

  const activeFloor = snapshot?.floors.find((floor) => floor.id === activeFloorId) ?? snapshot?.floors[0];
  const visibleObjects = React.useMemo(
    () =>
      snapshot?.objects.filter(
        (object) =>
          !object.deleted &&
          object.floorId === activeFloor?.id &&
          snapshot.layers.find((layer) => layer.id === object.layerId)?.visible !== false,
      ) ?? [],
    [activeFloor?.id, snapshot],
  );
  const selectedObjects = visibleObjects.filter((object) => selectedIds.includes(object.id));

  const commitSnapshot = React.useCallback(
    async (nextSnapshot: EditorSnapshot, operationType: string, objectId?: string | null) => {
      if (!snapshot) return;
      setSaveState("saving");
      const operation: EditorOperation = {
        clientOperationId: crypto.randomUUID(),
        createdAt: new Date().toISOString(),
        objectId: objectId ?? null,
        payload: { snapshot: nextSnapshot },
        type: "snapshot.replace",
      };
      try {
        await actions.applyOperations.mutateAsync({
          baseRevision: revision,
          clientBatchId: crypto.randomUUID(),
          operations: [{ ...operation, payload: { snapshot: nextSnapshot, reason: operationType } }],
        });
        setRevision((current) => current + 1);
        setSaveState("saved");
      } catch (error) {
        setSaveState(error instanceof Error && error.message.includes("changed") ? "conflict" : "error");
      }
    },
    [actions.applyOperations, revision, snapshot],
  );

  const pushLocalSnapshot = React.useCallback(
    (nextSnapshot: EditorSnapshot, operationType: string, objectId?: string | null) => {
      if (!snapshot) return;
      setUndoStack((current) => [...current.slice(-49), snapshot]);
      setRedoStack([]);
      setSnapshot(nextSnapshot);
      setSaveState("local");
      void commitSnapshot(nextSnapshot, operationType, objectId);
    },
    [commitSnapshot, snapshot],
  );

  const updateSelectedPoints = React.useCallback(
    (objectId: string, points: EditorPoint[]) => {
      if (!snapshot) return;
      const nextSnapshot = {
        ...snapshot,
        objects: snapshot.objects.map((object) =>
          object.id === objectId ? { ...object, points, revisionUpdated: revision + 1 } : object,
        ),
      };
      pushLocalSnapshot(nextSnapshot, "move", objectId);
    },
    [pushLocalSnapshot, revision, snapshot],
  );

  const undo = React.useCallback(() => {
    if (!snapshot || undoStack.length === 0) return;
    const previous = undoStack[undoStack.length - 1];
    setUndoStack((current) => current.slice(0, -1));
    setRedoStack((current) => [...current, snapshot]);
    setSnapshot(previous);
    setSaveState("local");
    void commitSnapshot(previous, "undo");
  }, [commitSnapshot, snapshot, undoStack]);

  const redo = React.useCallback(() => {
    if (!snapshot || redoStack.length === 0) return;
    const next = redoStack[redoStack.length - 1];
    setRedoStack((current) => current.slice(0, -1));
    setUndoStack((current) => [...current, snapshot]);
    setSnapshot(next);
    setSaveState("local");
    void commitSnapshot(next, "redo");
  }, [commitSnapshot, redoStack, snapshot]);

  React.useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z" && !event.shiftKey) {
        event.preventDefault();
        undo();
        return;
      }
      if (
        ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "y") ||
        ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === "z")
      ) {
        event.preventDefault();
        redo();
        return;
      }
      const keyMap: Partial<Record<string, EditorToolId>> = {
        d: "door",
        n: "window",
        r: "room",
        s: "stair",
        v: "select",
        w: "wall",
      };
      const tool = keyMap[event.key.toLowerCase()];
      if (tool) setActiveTool(tool);
      if (event.key === "Escape") {
        setDrag(null);
        setSelectedIds([]);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [redo, undo]);

  if (editor.isLoading) return <EditorSkeleton />;
  if (editor.isError) {
    return (
      <div className="compose-editor-light rounded-[1.75rem] border border-amber-200 bg-white p-6">
        <h1 className="text-lg font-semibold text-slate-950">2D editor unavailable</h1>
        <p className="mt-2 text-sm text-slate-600">
          Accept a conceptual floor-plan option before opening the editor.
        </p>
        <div className="mt-5 flex gap-3">
          <Button asChild variant="outline">
            <Link href={`/projects/${projectId}/floor-plans`}>Open floor plans</Link>
          </Button>
          <Button onClick={() => editor.refetch()} variant="outline">
            Retry
          </Button>
        </div>
      </div>
    );
  }
  if (!snapshot || !activeFloor || !editor.data) return <EditorSkeleton />;

  return (
    <div className="compose-editor-light -mx-4 -my-6 min-h-[calc(100dvh-4rem)] px-4 py-5 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
      <div className="mx-auto flex max-w-[96rem] flex-col gap-4">
        <EditorHeader document={editor.data} saveState={saveState} />
        <div className="rounded-[1.65rem] border border-white/80 bg-white/90 shadow-[0_24px_80px_rgba(51,65,85,0.10)] backdrop-blur-xl">
          <Toolbar
            activeTool={activeTool}
            onCheckpoint={() => actions.createCheckpoint.mutate(`Checkpoint r${revision}`)}
            onRedo={redo}
            onTool={setActiveTool}
            onUndo={undo}
            onValidate={() => actions.validate.mutate()}
            onZoomIn={() => setZoom((current) => Math.min(8, current + 0.1))}
            onZoomOut={() => setZoom((current) => Math.max(0.1, current - 0.1))}
            registry={editor.data.toolRegistry}
            redoDisabled={!redoStack.length}
            undoDisabled={!undoStack.length}
          />
          <div className="grid min-h-[42rem] grid-cols-1 border-t border-slate-200 lg:grid-cols-[16rem_minmax(0,1fr)_20rem]">
            <LayerPanel
              activeFloorId={activeFloor.id}
              floors={snapshot.floors}
              layers={snapshot.layers}
              onFloor={setActiveFloorId}
              onToggleLayer={(layerId) =>
                setSnapshot((current) =>
                  current
                    ? {
                        ...current,
                        layers: current.layers.map((layer) =>
                          layer.id === layerId ? { ...layer, visible: !layer.visible } : layer,
                        ),
                      }
                    : current,
                )
              }
            />
            <div className="min-w-0 border-y border-slate-200 bg-slate-50/80 lg:border-x lg:border-y-0">
              <CanvasSurface
                activeFloor={activeFloor}
                activeTool={activeTool}
                drag={drag}
                objects={visibleObjects}
                onCommit={pushLocalSnapshot}
                onDrag={setDrag}
                onMeasurement={setMeasurement}
                onSelect={(objectId, additive) =>
                  setSelectedIds((current) =>
                    additive
                      ? current.includes(objectId)
                        ? current.filter((id) => id !== objectId)
                        : [...current, objectId]
                      : [objectId],
                  )
                }
                renderer={renderer}
                selectedIds={selectedIds}
                snapshot={snapshot}
                updateSelectedPoints={updateSelectedPoints}
                zoom={zoom}
              />
              <StatusBar
                activeTool={activeTool}
                measurement={measurement}
                revision={revision}
                saveState={saveState}
                validationCount={editor.data.validationSummary.issueCount}
                zoom={zoom}
              />
            </div>
            <Inspector
              document={editor.data}
              history={history.data?.items ?? editor.data.history}
              issues={editor.data.validationIssues}
              onRestore={(checkpointId) => actions.restoreCheckpoint.mutate(checkpointId)}
              selectedObjects={selectedObjects}
              tab={inspectorTab}
              tabs={editor.data.inspectorTabs}
              setTab={setInspectorTab}
            />
          </div>
        </div>
        <p className="text-xs text-slate-500">{editor.data.disclaimer}</p>
      </div>
    </div>
  );
}

function EditorHeader({ document, saveState }: { document: EditorDocument; saveState: string }) {
  return (
    <section className="relative overflow-hidden rounded-[1.75rem] border border-white/80 bg-white/86 p-5 shadow-[0_18px_55px_rgba(51,65,85,0.08)] backdrop-blur-xl">
      <div aria-hidden="true" className="compose-editor-grid" />
      <div className="relative z-10 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-violet-200 bg-white/80 px-3 py-1 text-xs font-medium text-violet-700">
            <DraftingCompass className="size-3.5" aria-hidden="true" />
            Interactive 2D Editor
          </div>
          <h1 className="mt-3 text-2xl font-semibold text-slate-950 sm:text-3xl">Floor plan workspace</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Edit conceptual geometry with snap-aware tools, validation, checkpoints, and operation history.
          </p>
        </div>
        <div className="grid gap-2 text-xs text-slate-500 sm:grid-cols-3">
          <Metric label="Revision" value={`r${document.currentRevision}`} />
          <Metric label="Renderer" value="SVG MVP" />
          <Metric label="Autosave" value={saveState} />
        </div>
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white/86 px-4 py-3 shadow-sm">
      <p>{label}</p>
      <p className="mt-1 font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function Toolbar({
  activeTool,
  onCheckpoint,
  onRedo,
  onTool,
  onUndo,
  onValidate,
  onZoomIn,
  onZoomOut,
  registry,
  redoDisabled,
  undoDisabled,
}: {
  activeTool: EditorToolId;
  onCheckpoint: () => void;
  onRedo: () => void;
  onTool: (tool: EditorToolId) => void;
  onUndo: () => void;
  onValidate: () => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  registry: EditorToolDefinition[];
  redoDisabled: boolean;
  undoDisabled: boolean;
}) {
  return (
    <div className="flex flex-col gap-3 p-3 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex flex-wrap gap-2">
        {registry.map((tool) => {
          const Icon = toolIcons[tool.id];
          return (
            <button
              aria-pressed={activeTool === tool.id}
              className={cn(
                "flex h-10 items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 text-sm font-medium text-slate-600 shadow-sm transition hover:border-violet-200 hover:text-slate-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-300",
                activeTool === tool.id && "border-violet-200 bg-violet-50 text-violet-800",
              )}
              key={tool.id}
              onClick={() => onTool(tool.id)}
              title={tool.shortcut ? `${tool.label} (${tool.shortcut})` : tool.label}
              type="button"
            >
              <Icon className="size-4" aria-hidden="true" />
              <span className="hidden xl:inline">{tool.label}</span>
            </button>
          );
        })}
      </div>
      <div className="flex flex-wrap gap-2">
        <IconAction disabled={undoDisabled} label="Undo" onClick={onUndo} icon={Undo2} />
        <IconAction disabled={redoDisabled} label="Redo" onClick={onRedo} icon={Redo2} />
        <IconAction label="Zoom out" onClick={onZoomOut} icon={ZoomOut} />
        <IconAction label="Zoom in" onClick={onZoomIn} icon={ZoomIn} />
        <IconAction label="Validate" onClick={onValidate} icon={CheckCircle2} />
        <IconAction label="Checkpoint" onClick={onCheckpoint} icon={Save} />
      </div>
    </div>
  );
}

function IconAction({
  disabled,
  icon: Icon,
  label,
  onClick,
}: {
  disabled?: boolean;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      className="flex size-10 items-center justify-center rounded-2xl border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:border-violet-200 hover:text-slate-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-300 disabled:opacity-40"
      disabled={disabled}
      onClick={onClick}
      title={label}
      type="button"
    >
      <Icon className="size-4" aria-hidden="true" />
      <span className="sr-only">{label}</span>
    </button>
  );
}

function LayerPanel({
  activeFloorId,
  floors,
  layers,
  onFloor,
  onToggleLayer,
}: {
  activeFloorId: string;
  floors: EditorFloor[];
  layers: EditorSnapshot["layers"];
  onFloor: (floorId: string) => void;
  onToggleLayer: (layerId: string) => void;
}) {
  return (
    <aside className="space-y-5 p-4">
      <PanelTitle icon={Layers3} title="Floors" />
      <div className="grid gap-2">
        {floors.map((floor) => (
          <button
            className={cn(
              "rounded-2xl border border-slate-200 bg-white px-3 py-2 text-left text-sm shadow-sm",
              activeFloorId === floor.id && "border-violet-200 bg-violet-50 text-violet-800",
            )}
            key={floor.id}
            onClick={() => onFloor(floor.id)}
            type="button"
          >
            {floor.name}
          </button>
        ))}
      </div>
      <PanelTitle icon={Grid3X3} title="Layers" />
      <div className="grid gap-2">
        {layers.map((layer) => (
          <button
            className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm"
            key={layer.id}
            onClick={() => onToggleLayer(layer.id)}
            type="button"
          >
            <span>{layer.label}</span>
            <span className="flex items-center gap-2 text-xs text-slate-500">
              {layer.objectCount}
              {layer.visible ? <Eye className="size-4" /> : <EyeOff className="size-4" />}
            </span>
          </button>
        ))}
      </div>
      <PanelTitle icon={Focus} title="Snapping" />
      <div className="flex flex-wrap gap-1.5 text-xs">
        {["Corner", "Intersection", "Parallel", "Perpendicular", "Center", "Equal spacing"].map((item) => (
          <span className="rounded-full border border-blue-200 bg-blue-50 px-2 py-1 text-blue-700" key={item}>
            {item}
          </span>
        ))}
      </div>
    </aside>
  );
}

function CanvasSurface({
  activeFloor,
  activeTool,
  drag,
  objects,
  onCommit,
  onDrag,
  onMeasurement,
  onSelect,
  selectedIds,
  snapshot,
  updateSelectedPoints,
  zoom,
}: {
  activeFloor: EditorFloor;
  activeTool: EditorToolId;
  drag: DragState;
  objects: EditorObject[];
  onCommit: (snapshot: EditorSnapshot, operationType: string, objectId?: string | null) => void;
  onDrag: (state: DragState) => void;
  onMeasurement: (value: string) => void;
  onSelect: (objectId: string, additive: boolean) => void;
  renderer: RendererKind;
  selectedIds: string[];
  snapshot: EditorSnapshot;
  updateSelectedPoints: (objectId: string, points: EditorPoint[]) => void;
  zoom: number;
}) {
  const bounds = activeFloor.bounds;
  const width = Math.max(8000, bounds.maxX - bounds.minX + 2000);
  const height = Math.max(6000, bounds.maxY - bounds.minY + 2000);
  const viewBox = `${bounds.minX - 1000} ${bounds.minY - 1000} ${width} ${height}`;

  const pointerPoint = (event: React.PointerEvent<SVGSVGElement>): EditorPoint => {
    const svg = event.currentTarget;
    const point = svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    const transformed = point.matrixTransform(svg.getScreenCTM()?.inverse());
    return snapPoint({ x: transformed.x, y: transformed.y });
  };

  const createObject = (type: "wall" | "room", start: EditorPoint, end: EditorPoint) => {
    const id = `${type}-${crypto.randomUUID()}`;
    const object: EditorObject =
      type === "wall"
        ? {
            deleted: false,
            floorId: activeFloor.id,
            height: null,
            id,
            layerId: "walls",
            metadata: { thicknessMm: 150 },
            name: "Wall",
            points: [start, end],
            position: null,
            revisionCreated: 0,
            revisionUpdated: 0,
            type: "wall",
            wallId: null,
            width: null,
          }
        : {
            deleted: false,
            floorId: activeFloor.id,
            height: null,
            id,
            layerId: "rooms",
            metadata: { areaM2: polygonArea(rectPoints(start, end)) / 1_000_000 },
            name: "New room",
            points: rectPoints(start, end),
            position: null,
            revisionCreated: 0,
            revisionUpdated: 0,
            type: "room",
            wallId: null,
            width: null,
          };
    onCommit({ ...snapshot, objects: [...snapshot.objects, object] }, `${type}.create`, id);
    onSelect(id, false);
  };

  return (
    <div className="relative min-h-[34rem] overflow-hidden">
      <svg
        aria-label={`2D floor plan canvas for ${activeFloor.name}`}
        className="compose-editor-canvas h-[34rem] w-full touch-none"
        onPointerDown={(event) => {
          const point = pointerPoint(event);
          if (activeTool === "wall") onDrag({ current: point, mode: "draw-wall", start: point });
          if (activeTool === "room") onDrag({ current: point, mode: "draw-room", start: point });
        }}
        onPointerMove={(event) => {
          if (!drag) return;
          const point = pointerPoint(event);
          if (drag.mode === "draw-wall" || drag.mode === "draw-room") {
            onDrag({ ...drag, current: point });
            const length = distance(drag.start, point);
            const area = drag.mode === "draw-room" ? polygonArea(rectPoints(drag.start, point)) / 1_000_000 : null;
            onMeasurement(area ? `Length ${formatMm(length)} · Area ${area.toFixed(2)} m2` : `Length ${formatMm(length)} · Angle ${angle(drag.start, point).toFixed(0)}°`);
          }
        }}
        onPointerUp={() => {
          if (!drag) return;
          if (drag.mode === "draw-wall") createObject("wall", drag.start, drag.current);
          if (drag.mode === "draw-room") createObject("room", drag.start, drag.current);
          if (drag.mode === "move") updateSelectedPoints(drag.objectId, drag.original);
          onDrag(null);
        }}
        role="application"
        style={{ transform: `scale(${zoom})`, transformOrigin: "center" }}
        tabIndex={0}
        viewBox={viewBox}
      >
        <defs>
          <pattern height="500" id="editor-grid" patternUnits="userSpaceOnUse" width="500">
            <path d="M 500 0 L 0 0 0 500" fill="none" stroke="rgb(148 163 184 / 0.22)" strokeWidth="12" />
          </pattern>
        </defs>
        <rect fill="url(#editor-grid)" height={height * 2} width={width * 2} x={bounds.minX - 2000} y={bounds.minY - 2000} />
        {objects.map((object) => (
          <EditorSvgObject
            key={object.id}
            object={object}
            onSelect={onSelect}
            selected={selectedIds.includes(object.id)}
          />
        ))}
        {drag?.mode === "draw-wall" ? (
          <line className="stroke-blue-500" strokeDasharray="160 120" strokeWidth="90" x1={drag.start.x} x2={drag.current.x} y1={drag.start.y} y2={drag.current.y} />
        ) : null}
        {drag?.mode === "draw-room" ? (
          <polygon className="fill-violet-400/15 stroke-violet-500" points={pointsAttr(rectPoints(drag.start, drag.current))} strokeDasharray="160 120" strokeWidth="80" />
        ) : null}
      </svg>
      <div className="pointer-events-none absolute left-4 top-4 rounded-2xl border border-white/80 bg-white/90 px-3 py-2 text-xs text-slate-600 shadow-sm">
        Live measurement: {snapshot.measurementOverlay?.length ?? "Ready"}
      </div>
      <div className="absolute bottom-4 right-4 hidden rounded-2xl border border-slate-200 bg-white/90 px-3 py-2 text-xs text-slate-600 shadow-sm md:block">
        Tablet/mobile editing is limited. Desktop recommended.
      </div>
    </div>
  );
}

function EditorSvgObject({
  object,
  onSelect,
  selected,
}: {
  object: EditorObject;
  onSelect: (objectId: string, additive: boolean) => void;
  selected: boolean;
}) {
  const common = {
    onClick: (event: React.MouseEvent) => {
      event.stopPropagation();
      onSelect(object.id, event.shiftKey);
    },
  };
  if (object.type === "room" || object.type === "stair") {
    return (
      <polygon
        {...common}
        className={cn("cursor-pointer fill-white/80 stroke-slate-400 transition", selected && "fill-violet-100 stroke-violet-600")}
        points={pointsAttr(object.points)}
        strokeWidth="80"
      />
    );
  }
  if (object.type === "wall") {
    const [start, end] = object.points;
    if (!start || !end) return null;
    return (
      <line
        {...common}
        className={cn("cursor-pointer stroke-slate-700 transition", selected && "stroke-violet-600")}
        strokeLinecap="round"
        strokeWidth={Number(object.metadata.thicknessMm ?? 150)}
        x1={start.x}
        x2={end.x}
        y1={start.y}
        y2={end.y}
      />
    );
  }
  if (object.type === "opening") {
    const [start, end] = object.points;
    if (!start || !end) return null;
    return (
      <line
        {...common}
        className={cn("cursor-pointer stroke-blue-500 transition", selected && "stroke-violet-700")}
        strokeLinecap="round"
        strokeWidth="90"
        x1={start.x}
        x2={end.x}
        y1={start.y}
        y2={end.y}
      />
    );
  }
  return null;
}

function Inspector({
  document,
  history,
  issues,
  onRestore,
  selectedObjects,
  setTab,
  tab,
  tabs,
}: {
  document: EditorDocument;
  history: EditorDocument["history"];
  issues: EditorValidationIssue[];
  onRestore: (checkpointId: string) => void;
  selectedObjects: EditorObject[];
  setTab: (tab: EditorInspectorTab) => void;
  tab: EditorInspectorTab;
  tabs: EditorInspectorTab[];
}) {
  return (
    <aside className="min-w-0 p-4">
      <PanelTitle icon={PanelRight} title="Inspector" />
      <div className="mt-3 grid grid-cols-2 gap-2">
        {tabs.map((item) => (
          <button
            className={cn("rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs font-medium capitalize text-slate-600", tab === item && "border-violet-200 bg-violet-50 text-violet-800")}
            key={item}
            onClick={() => setTab(item)}
            type="button"
          >
            {item}
          </button>
        ))}
      </div>
      <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-4 text-sm shadow-sm">
        {tab === "properties" ? <PropertiesTab document={document} selectedObjects={selectedObjects} /> : null}
        {tab === "validation" ? <ValidationTab issues={issues} /> : null}
        {tab === "metadata" ? <MetadataTab selectedObjects={selectedObjects} /> : null}
        {tab === "history" ? <HistoryTab history={history} onRestore={onRestore} /> : null}
      </div>
    </aside>
  );
}

function PropertiesTab({ document, selectedObjects }: { document: EditorDocument; selectedObjects: EditorObject[] }) {
  if (!selectedObjects.length) {
    return (
      <div>
        <p className="font-semibold text-slate-950">Document summary</p>
        <dl className="mt-3 grid gap-2 text-xs text-slate-600">
          <div className="flex justify-between"><dt>Floors</dt><dd>{document.snapshot.floors.length}</dd></div>
          <div className="flex justify-between"><dt>Objects</dt><dd>{document.snapshot.objects.filter((item) => !item.deleted).length}</dd></div>
          <div className="flex justify-between"><dt>Revision</dt><dd>r{document.currentRevision}</dd></div>
        </dl>
      </div>
    );
  }
  return (
    <div>
      <p className="font-semibold text-slate-950">{selectedObjects.length === 1 ? selectedObjects[0]?.name : `${selectedObjects.length} objects selected`}</p>
      <dl className="mt-3 grid gap-2 text-xs text-slate-600">
        <div className="flex justify-between"><dt>Type</dt><dd>{selectedObjects[0]?.type}</dd></div>
        <div className="flex justify-between"><dt>Points</dt><dd>{selectedObjects[0]?.points.length}</dd></div>
        <div className="flex justify-between"><dt>Layer</dt><dd>{selectedObjects[0]?.layerId}</dd></div>
      </dl>
    </div>
  );
}

function ValidationTab({ issues }: { issues: EditorValidationIssue[] }) {
  if (!issues.length) {
    return <p className="text-sm text-slate-600">No validation issues in the latest server check.</p>;
  }
  return (
    <div className="grid gap-3">
      {issues.map((issue) => (
        <div className="rounded-2xl border border-amber-200 bg-amber-50/70 p-3" key={issue.id}>
          <p className="flex items-center gap-2 text-sm font-semibold text-slate-950">
            <AlertTriangle className="size-4 text-amber-600" aria-hidden="true" />
            {issue.code}
          </p>
          <p className="mt-1 text-xs leading-5 text-slate-600">{issue.message}</p>
        </div>
      ))}
    </div>
  );
}

function MetadataTab({ selectedObjects }: { selectedObjects: EditorObject[] }) {
  const metadata = selectedObjects[0]?.metadata ?? {};
  return <pre className="max-h-72 overflow-auto text-xs text-slate-600">{JSON.stringify(metadata, null, 2)}</pre>;
}

function HistoryTab({ history, onRestore }: { history: EditorDocument["history"]; onRestore: (checkpointId: string) => void }) {
  return (
    <div className="grid gap-3">
      {history.map((item) => (
        <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-3" key={item.id}>
          <p className="flex items-center gap-2 text-sm font-semibold text-slate-950">
            <History className="size-4 text-violet-600" aria-hidden="true" />
            {item.title}
          </p>
          <p className="mt-1 text-xs text-slate-500">Revision r{item.revision} · {new Date(item.createdAt).toLocaleString()}</p>
          {item.itemType === "checkpoint" ? (
            <button className="mt-2 text-xs font-semibold text-violet-700 hover:underline" onClick={() => onRestore(item.id)} type="button">
              Restore as new revision
            </button>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function StatusBar({
  activeTool,
  measurement,
  revision,
  saveState,
  validationCount,
  zoom,
}: {
  activeTool: string;
  measurement: string;
  revision: number;
  saveState: string;
  validationCount: number;
  zoom: number;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 bg-white/80 px-4 py-3 text-xs text-slate-600">
      <span>Tool: {activeTool}</span>
      <span>{measurement}</span>
      <span>Zoom: {Math.round(zoom * 100)}%</span>
      <span>Revision r{revision}</span>
      <span>{validationCount} validation issues</span>
      <span className="flex items-center gap-1"><Clock3 className="size-3.5" /> {saveState}</span>
    </div>
  );
}

function PanelTitle({ icon: Icon, title }: { icon: React.ComponentType<{ className?: string }>; title: string }) {
  return (
    <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-950">
      <Icon className="size-4 text-violet-600" aria-hidden="true" />
      {title}
    </h2>
  );
}

function EditorSkeleton() {
  return (
    <div className="compose-editor-light space-y-4">
      <Skeleton className="h-36 w-full rounded-[1.75rem]" />
      <Skeleton className="h-[42rem] w-full rounded-[1.75rem]" />
    </div>
  );
}

function pointsAttr(points: EditorPoint[]): string {
  return points.map((point) => `${point.x},${point.y}`).join(" ");
}

function rectPoints(start: EditorPoint, end: EditorPoint): EditorPoint[] {
  return [start, { x: end.x, y: start.y }, end, { x: start.x, y: end.y }];
}

function snapPoint(point: EditorPoint): EditorPoint {
  const grid = 100;
  return { x: Math.round(point.x / grid) * grid, y: Math.round(point.y / grid) * grid };
}

function distance(start: EditorPoint, end: EditorPoint): number {
  return Math.hypot(end.x - start.x, end.y - start.y);
}

function angle(start: EditorPoint, end: EditorPoint): number {
  return (Math.atan2(end.y - start.y, end.x - start.x) * 180) / Math.PI;
}

function polygonArea(points: EditorPoint[]): number {
  return Math.abs(
    points.reduce((sum, point, index) => {
      const next = points[(index + 1) % points.length] ?? point;
      return sum + point.x * next.y - next.x * point.y;
    }, 0) / 2,
  );
}

function formatMm(value: number): string {
  if (value >= 1000) return `${(value / 1000).toFixed(2)} m`;
  return `${Math.round(value)} mm`;
}
