"use client";

import type {
  FloorPlanGeometry,
  FloorPlanPoint,
  FloorPlanSpace,
} from "@compose-ai/shared";
import { Maximize2, Minus, Plus } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface FloorPlanPreviewProps {
  compact?: boolean;
  floorIndex?: number;
  geometry: FloorPlanGeometry;
  onFloorChange?: (floorIndex: number) => void;
}

const zoneClasses: Record<FloorPlanSpace["zone"], string> = {
  public: "fill-violet-100 stroke-violet-400",
  private: "fill-blue-50 stroke-blue-400",
  service: "fill-amber-50 stroke-amber-400",
  circulation: "fill-slate-100 stroke-slate-400",
};

const minZoom = 1;
const maxZoom = 2.5;
const zoomStep = 0.25;

export function FloorPlanPreview({
  compact = false,
  floorIndex = 0,
  geometry,
  onFloorChange,
}: FloorPlanPreviewProps) {
  const reducedMotion = useReducedMotion();
  const [zoom, setZoom] = React.useState(1);
  const floor = geometry.floors.find((item) => item.index === floorIndex) ?? geometry.floors[0];
  const bounds = polygonBounds(geometry.plotBoundary);
  const padding = Math.max(500, Math.round(Math.max(bounds.width, bounds.height) * 0.04));
  const viewBox = [
    bounds.minX - padding,
    bounds.minY - padding,
    bounds.width + padding * 2,
    bounds.height + padding * 2,
  ].join(" ");

  React.useEffect(() => {
    setZoom(1);
  }, [floor?.index]);

  if (!floor) return null;

  const changeZoom = (next: number) => {
    setZoom(Math.max(minZoom, Math.min(maxZoom, Number(next.toFixed(2)))));
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (compact) return;
    if (event.key === "+" || event.key === "=") {
      event.preventDefault();
      changeZoom(zoom + zoomStep);
    }
    if (event.key === "-") {
      event.preventDefault();
      changeZoom(zoom - zoomStep);
    }
    if (event.key === "0") {
      event.preventDefault();
      changeZoom(1);
    }
  };

  const drawing = (
    <svg
      aria-label={`${floor.name} conceptual floor plan`}
      className="size-full"
      preserveAspectRatio="xMidYMid meet"
      role="img"
      viewBox={viewBox}
    >
      <title>{`${floor.name}. Conceptual Design - Not for Construction.`}</title>
      <polygon
        className="fill-transparent stroke-slate-400"
        fill="none"
        points={points(geometry.plotBoundary)}
        strokeDasharray="320 180"
        strokeWidth={compact ? 90 : 70}
        vectorEffect="non-scaling-stroke"
      />
      <polygon
        className="fill-transparent stroke-violet-300"
        fill="none"
        points={points(geometry.buildableEnvelope)}
        strokeDasharray="180 120"
        strokeWidth={compact ? 70 : 55}
        vectorEffect="non-scaling-stroke"
      />
      <polygon
        className="fill-white stroke-slate-300"
        points={points(floor.envelope)}
        strokeWidth={compact ? 90 : 70}
        vectorEffect="non-scaling-stroke"
      />
      <polygon
        className="fill-slate-100 stroke-slate-400"
        points={points(floor.circulation.polygon)}
        strokeWidth={55}
        vectorEffect="non-scaling-stroke"
      />
      {[...floor.rooms, ...floor.stairs, ...floor.parking, ...floor.balconies].map((space) => (
        <SpacePolygon compact={compact} key={space.id} space={space} />
      ))}
      {floor.walls.map((wall) => (
        <line
          className={wall.exterior ? "stroke-slate-900" : "stroke-slate-500"}
          key={wall.id}
          strokeLinecap="square"
          strokeWidth={wall.exterior ? 3 : 2}
          vectorEffect="non-scaling-stroke"
          x1={wall.start[0]}
          x2={wall.end[0]}
          y1={wall.start[1]}
          y2={wall.end[1]}
        />
      ))}
      {floor.windows.map((window) => (
        <line
          className="stroke-blue-500"
          key={window.id}
          strokeLinecap="round"
          strokeWidth={compact ? 4 : 6}
          vectorEffect="non-scaling-stroke"
          x1={window.start[0]}
          x2={window.end[0]}
          y1={window.start[1]}
          y2={window.end[1]}
        />
      ))}
      {floor.doors.map((door) => (
        <line
          className="stroke-amber-500"
          key={door.id}
          strokeLinecap="round"
          strokeWidth={compact ? 3 : 5}
          vectorEffect="non-scaling-stroke"
          x1={door.start[0]}
          x2={door.end[0]}
          y1={door.start[1]}
          y2={door.end[1]}
        />
      ))}
      {!compact ? <NorthIndicator bounds={bounds} /> : null}
    </svg>
  );

  return (
    <div className={cn("space-y-3", !compact && "p-3 sm:p-4")}>
      {!compact && geometry.floors.length > 1 ? (
        <div aria-label="Floor preview" className="flex flex-wrap gap-1" role="group">
          {geometry.floors.map((item) => (
            <Button
              aria-pressed={item.index === floor.index}
              className={cn(item.index === floor.index && "text-violet-700")}
              key={item.index}
              onClick={() => onFloorChange?.(item.index)}
              size="sm"
              type="button"
              variant={item.index === floor.index ? "secondary" : "ghost"}
            >
              {item.name}
            </Button>
          ))}
        </div>
      ) : null}

      <div
        aria-label={compact ? undefined : "Floor plan preview. Use plus and minus keys to zoom."}
        className={cn(
          "compose-floor-canvas relative aspect-[4/3] w-full overflow-hidden bg-slate-50",
          !compact &&
            "min-h-[320px] rounded-lg border border-slate-200 outline-none focus-visible:ring-2 focus-visible:ring-violet-500 sm:min-h-[500px]",
        )}
        onKeyDown={handleKeyDown}
        tabIndex={compact ? undefined : 0}
      >
        {!compact ? (
          <div className="absolute right-3 top-3 z-10 flex items-center rounded-md border border-slate-200 bg-white/95 p-1 shadow-sm backdrop-blur-sm">
            <Button
              aria-label="Zoom out"
              disabled={zoom <= minZoom}
              onClick={() => changeZoom(zoom - zoomStep)}
              size="icon"
              title="Zoom out (-)"
              variant="ghost"
            >
              <Minus aria-hidden="true" />
            </Button>
            <span aria-live="polite" className="w-12 text-center text-xs font-medium tabular-nums text-slate-600">
              {Math.round(zoom * 100)}%
            </span>
            <Button
              aria-label="Zoom in"
              disabled={zoom >= maxZoom}
              onClick={() => changeZoom(zoom + zoomStep)}
              size="icon"
              title="Zoom in (+)"
              variant="ghost"
            >
              <Plus aria-hidden="true" />
            </Button>
            <span aria-hidden="true" className="mx-1 h-5 w-px bg-slate-200" />
            <Button
              aria-label="Fit floor plan"
              disabled={zoom === 1}
              onClick={() => changeZoom(1)}
              size="icon"
              title="Fit to view (0)"
              variant="ghost"
            >
              <Maximize2 aria-hidden="true" />
            </Button>
          </div>
        ) : null}

        {compact ? (
          drawing
        ) : (
          <AnimatePresence initial={false} mode="wait">
            <motion.div
              animate={{ opacity: 1, scale: zoom }}
              className="absolute inset-0"
              exit={reducedMotion ? undefined : { opacity: 0 }}
              initial={reducedMotion ? false : { opacity: 0.35 }}
              key={floor.index}
              style={{ transformOrigin: "center" }}
              transition={{ duration: reducedMotion ? 0 : 0.24, ease: "easeOut" }}
            >
              {drawing}
            </motion.div>
          </AnimatePresence>
        )}

        {!compact ? (
          <>
            <div className="pointer-events-none absolute bottom-3 left-3 z-10 rounded-md border border-slate-200 bg-white/95 px-2 py-1 text-[11px] text-slate-500 shadow-sm">
              Non-editable preview
            </div>
            <div className="pointer-events-none absolute bottom-3 right-3 z-10 hidden items-center gap-3 rounded-md border border-slate-200 bg-white/95 px-2.5 py-1.5 text-[10px] text-slate-500 shadow-sm sm:flex">
              <LegendDot className="bg-violet-200" label="Public" />
              <LegendDot className="bg-blue-100" label="Private" />
              <LegendDot className="bg-amber-100" label="Service" />
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}

function LegendDot({ className, label }: { className: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={cn("size-2 rounded-sm border border-slate-300", className)} />
      {label}
    </span>
  );
}

function SpacePolygon({ compact, space }: { compact: boolean; space: FloorPlanSpace }) {
  const bounds = polygonBounds(space.polygon);
  const showLabel = !compact && bounds.width >= 1_800 && bounds.height >= 1_400;
  const labelSize = Math.max(240, Math.min(380, Math.min(bounds.width, bounds.height) * 0.12));
  const centerX = bounds.minX + bounds.width / 2;
  const centerY = bounds.minY + bounds.height / 2;
  return (
    <g>
      <title>{`${space.name}, ${space.areaM2.toFixed(1)} square metres`}</title>
      <polygon
        className={zoneClasses[space.zone]}
        points={points(space.polygon)}
        strokeWidth={50}
        vectorEffect="non-scaling-stroke"
      />
      {showLabel ? (
        <text
          className="pointer-events-none select-none fill-slate-800"
          fontSize={labelSize}
          textAnchor="middle"
          x={centerX}
          y={centerY}
        >
          <tspan x={centerX}>{truncate(space.name, 20)}</tspan>
          <tspan className="fill-slate-500" dy={labelSize * 1.1} x={centerX}>
            {space.areaM2.toFixed(1)} m2
          </tspan>
        </text>
      ) : null}
    </g>
  );
}

function NorthIndicator({ bounds }: { bounds: ReturnType<typeof polygonBounds> }) {
  const size = Math.max(700, Math.min(bounds.width, bounds.height) * 0.08);
  const x = bounds.maxX - size * 0.7;
  const y = bounds.minY + size * 0.9;
  return (
    <g aria-label="North indicator">
      <line
        className="stroke-slate-800"
        strokeWidth={2}
        vectorEffect="non-scaling-stroke"
        x1={x}
        x2={x}
        y1={y + size * 0.5}
        y2={y - size * 0.3}
      />
      <path
        className="fill-slate-800"
        d={`M ${x} ${y - size * 0.5} L ${x - size * 0.18} ${y - size * 0.12} L ${x + size * 0.18} ${y - size * 0.12} Z`}
      />
      <text
        className="fill-slate-800"
        fontSize={size * 0.36}
        fontWeight="600"
        textAnchor="middle"
        x={x}
        y={y + size * 0.9}
      >
        N
      </text>
    </g>
  );
}

function polygonBounds(polygon: FloorPlanPoint[]) {
  const x = polygon.map((point) => point[0]);
  const y = polygon.map((point) => point[1]);
  const minX = Math.min(...x);
  const maxX = Math.max(...x);
  const minY = Math.min(...y);
  const maxY = Math.max(...y);
  return { minX, maxX, minY, maxY, width: maxX - minX, height: maxY - minY };
}

function points(value: FloorPlanPoint[]): string {
  return value.map((point) => point.join(",")).join(" ");
}

function truncate(value: string, length: number): string {
  return value.length <= length ? value : `${value.slice(0, length - 3)}...`;
}
