"use client";

import type { FloorPlanOption } from "@compose-ai/shared";
import { AlertTriangle, Check, GitCompareArrows } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";

import { FloorPlanPreview } from "@/components/floor-plans/floor-plan-preview";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface FloorPlanOptionCardProps {
  compareSelected: boolean;
  index: number;
  onCompareChange: (selected: boolean) => void;
  onSelect: () => void;
  option: FloorPlanOption;
  selected: boolean;
}

export function FloorPlanOptionCard({
  compareSelected,
  index,
  onCompareChange,
  onSelect,
  option,
  selected,
}: FloorPlanOptionCardProps) {
  const reducedMotion = useReducedMotion();
  const warningCount = option.warnings.length + option.validation.warnings.length;
  const confidence = Math.max(0, Math.min(100, Math.round(option.confidence * 100)));

  return (
    <motion.article
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "compose-floor-option-card overflow-hidden rounded-lg border bg-white shadow-sm outline-none",
        selected ? "border-violet-400 ring-2 ring-violet-100" : "border-slate-200",
      )}
      initial={reducedMotion ? false : { opacity: 0, y: 10 }}
      transition={{ delay: reducedMotion ? 0 : index * 0.045, duration: 0.22, ease: "easeOut" }}
      whileHover={reducedMotion ? undefined : { y: -2 }}
    >
      <button
        aria-label={`Preview ${option.title}`}
        className="relative block aspect-[4/3] w-full bg-slate-50 text-left outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-violet-500"
        onClick={onSelect}
        type="button"
      >
        <FloorPlanPreview compact geometry={option.geometry} />
        {selected ? (
          <span className="absolute left-3 top-3 inline-flex h-7 items-center gap-1.5 rounded-md border border-violet-200 bg-white/95 px-2 text-[11px] font-semibold text-violet-700 shadow-sm backdrop-blur-sm">
            <Check aria-hidden="true" className="size-3.5" />
            Selected
          </span>
        ) : null}
      </button>

      <div className="space-y-4 border-t border-slate-200 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase text-violet-700">
              Option {option.optionNumber}
            </p>
            <h3 className="mt-1 truncate text-sm font-semibold text-slate-900">{option.title}</h3>
            <p className="mt-1 text-xs text-slate-500">
              {option.areaSummary.grossAreaM2?.toFixed(1) ?? "-"} m2 | Seed {option.deterministicSeed}
            </p>
          </div>
          <Badge
            className="rounded-md capitalize"
            variant={option.status === "accepted" ? "success" : "neutral"}
          >
            {option.status.replaceAll("_", " ")}
          </Badge>
        </div>

        <div>
          <div className="flex items-center justify-between text-xs">
            <span className="font-medium text-slate-600">Confidence</span>
            <span className="font-semibold tabular-nums text-slate-900">{confidence}%</span>
          </div>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
            <motion.div
              animate={{ width: `${confidence}%` }}
              className="h-full rounded-full bg-violet-600"
              initial={false}
              transition={{ duration: reducedMotion ? 0 : 0.28 }}
            />
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 text-xs text-slate-500">
          <span>Diversity {Math.round(option.diversityScore * 100)}%</span>
          <span
            className={cn(
              "inline-flex items-center gap-1.5",
              warningCount && "text-amber-700",
            )}
          >
            {warningCount ? <AlertTriangle aria-hidden="true" className="size-3.5" /> : null}
            {warningCount
              ? `${warningCount} warning${warningCount === 1 ? "" : "s"}`
              : "Validated"}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <Button
            className="compose-floor-action flex-1"
            onClick={onSelect}
            size="sm"
            variant="outline"
          >
            {selected ? <Check aria-hidden="true" /> : null}
            {selected ? "Selected" : "Review"}
          </Button>
          <label className="flex h-9 cursor-pointer items-center gap-2 rounded-md border border-slate-200 px-3 text-xs text-slate-500 transition-colors hover:border-violet-300 hover:bg-violet-50 hover:text-violet-700 focus-within:ring-2 focus-within:ring-violet-500">
            <input
              checked={compareSelected}
              className="size-4 accent-violet-600"
              onChange={(event) => onCompareChange(event.target.checked)}
              type="checkbox"
            />
            <GitCompareArrows aria-hidden="true" className="size-4" />
            Compare
          </label>
        </div>
      </div>
    </motion.article>
  );
}
