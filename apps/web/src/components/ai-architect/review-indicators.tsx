"use client";

import type { AISourceReference } from "@compose-ai/shared";
import { BookOpenText, ChevronDown } from "lucide-react";

import { cn } from "@/lib/utils";

export function ConfidenceIndicator({
  className,
  value,
}: {
  className?: string;
  value: number;
}) {
  const percentage = Math.max(0, Math.min(100, Math.round(value * 100)));
  const label = percentage >= 85 ? "High" : percentage >= 60 ? "Medium" : "Low";
  const tone =
    percentage >= 85
      ? "bg-emerald-500"
      : percentage >= 60
        ? "bg-amber-500"
        : "bg-rose-500";

  return (
    <div
      aria-label={`${label} confidence, ${percentage}%`}
      className={cn("w-24 shrink-0", className)}
      role="progressbar"
      aria-valuemax={100}
      aria-valuemin={0}
      aria-valuenow={percentage}
    >
      <div className="flex items-center justify-between gap-2 text-[11px] font-medium">
        <span className="text-slate-500">{label}</span>
        <span className="tabular-nums text-slate-700">{percentage}%</span>
      </div>
      <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-slate-200">
        <div className={cn("h-full rounded-full", tone)} style={{ width: `${percentage}%` }} />
      </div>
    </div>
  );
}

export function SourceReferences({ sources }: { sources: AISourceReference[] }) {
  if (!sources.length) return null;

  return (
    <details className="group mt-3 border-t border-slate-200/80 pt-3">
      <summary className="flex min-h-8 cursor-pointer list-none items-center gap-2 rounded-md text-xs font-medium text-slate-500 outline-none transition-colors hover:text-violet-700 focus-visible:ring-2 focus-visible:ring-violet-500/50 [&::-webkit-details-marker]:hidden">
        <BookOpenText aria-hidden="true" className="size-3.5" />
        {sources.length} {sources.length === 1 ? "source" : "sources"}
        <ChevronDown
          aria-hidden="true"
          className="ml-auto size-3.5 transition-transform duration-200 group-open:rotate-180"
        />
      </summary>
      <ul className="mt-2 space-y-2" aria-label="Source references">
        {sources.map((source, index) => (
          <li
            className="border-l-2 border-violet-200 pl-3 text-xs leading-5 text-slate-600"
            key={`${source.source_type}-${source.source_id ?? "source"}-${source.field_path ?? index}`}
          >
            <p className="font-medium text-slate-700">
              {formatSourceType(source.source_type)}
              {source.field_path ? (
                <span className="font-normal text-slate-500"> · {formatPath(source.field_path)}</span>
              ) : null}
            </p>
            {source.excerpt ? <p className="mt-0.5 text-slate-500">{source.excerpt}</p> : null}
          </li>
        ))}
      </ul>
    </details>
  );
}

function formatSourceType(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatPath(value: string): string {
  return value
    .replace(/^\//, "")
    .replaceAll("/", " / ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}
