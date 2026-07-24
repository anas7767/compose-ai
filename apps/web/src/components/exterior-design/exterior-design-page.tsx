"use client";

import type { ExteriorDesignStyle, ExteriorMaterialCategory } from "@compose-ai/shared";
import { AlertCircle, CheckCircle2, ImageIcon, Sparkles } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Panel } from "@/components/ui/panel";
import { SectionHeader } from "@/components/ui/section-header";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useExteriorActions,
  useExteriorOptions,
  useExteriorReadiness,
  useExteriorRuns,
} from "@/hooks/use-exterior-design";

interface ExteriorDesignPageProps {
  projectId: string;
}

const defaultMaterials: ExteriorMaterialCategory[] = ["paint", "glass", "concrete"];

export function ExteriorDesignPage({ projectId }: ExteriorDesignPageProps) {
  const readiness = useExteriorReadiness(projectId);
  const runs = useExteriorRuns(projectId);
  const options = useExteriorOptions(projectId);
  const actions = useExteriorActions(projectId);
  const [style, setStyle] = React.useState<ExteriorDesignStyle>("modern");
  const [instructions, setInstructions] = React.useState("");
  const [materials, setMaterials] = React.useState<ExteriorMaterialCategory[]>(defaultMaterials);
  const ready = readiness.data?.ready ?? false;

  const generate = async () => {
    await actions.generate.mutateAsync({
      style,
      viewType: "front",
      materialPreferences: materials,
      optionCount: 1,
      userInstructions: instructions || null,
      negativeConstraints: null,
      seed: null,
    });
  };

  if (readiness.isLoading) return <ExteriorSkeleton />;
  if (readiness.isError || !readiness.data) {
    return (
      <EmptyState
        action={<Button onClick={() => readiness.refetch()}>Retry</Button>}
        description="Compose could not load exterior design readiness for this project."
        icon={AlertCircle}
        title="Exterior readiness unavailable"
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="rounded-[2rem] border border-violet-100 bg-white/85 p-6 shadow-[0_20px_80px_rgba(70,50,120,0.08)] sm:p-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-violet-600">
              Phase 10A foundation
            </p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
              AI exterior design
            </h1>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              Generate conceptual front-elevation options from the accepted floor plan and compiled
              3D scene. Results remain conceptual and are not construction documents.
            </p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
            {readiness.data.disclaimer}
          </div>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-6">
          <Panel className="p-5 sm:p-6">
            <SectionHeader
              description="Compose verifies source design, 3D scene, and lineage before generation."
              title="Readiness"
            />
            <div className="mt-5 grid gap-3 md:grid-cols-3">
              <ReadinessPill
                ok={Boolean(readiness.data.sourceDesignVersionId)}
                title="Accepted design"
              />
              <ReadinessPill ok={Boolean(readiness.data.sourceSceneVersionId)} title="3D scene" />
              <ReadinessPill
                ok={Boolean(readiness.data.sourceEditorCheckpointId)}
                title="Editor checkpoint"
              />
            </div>
            {readiness.data.issues.length ? (
              <div className="mt-5 space-y-3">
                {readiness.data.issues.map((issue) => (
                  <div
                    className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
                    key={issue.code}
                  >
                    <p className="font-medium">{issue.message}</p>
                  </div>
                ))}
              </div>
            ) : null}
          </Panel>

          <Panel className="p-5 sm:p-6">
            <SectionHeader
              description="Phase 10A supports front elevation generation only."
              title="Generate front elevation"
            />
            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <label className="space-y-2 text-sm font-medium text-slate-700">
                Style
                <select
                  className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none transition focus:border-violet-300 focus:ring-4 focus:ring-violet-100"
                  onChange={(event) => setStyle(event.target.value as ExteriorDesignStyle)}
                  value={style}
                >
                  {readiness.data.supportedStyles.map((item) => (
                    <option key={item} value={item}>
                      {formatLabel(item)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-2 text-sm font-medium text-slate-700">
                View
                <input
                  className="h-11 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 text-sm text-slate-500"
                  readOnly
                  value="Front elevation"
                />
              </label>
            </div>
            <div className="mt-5">
              <p className="text-sm font-medium text-slate-700">Material preferences</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {readiness.data.materialLibrary.map((item) => {
                  const selected = materials.includes(item);
                  return (
                    <button
                      className={`rounded-full border px-3 py-1.5 text-sm transition ${
                        selected
                          ? "border-violet-300 bg-violet-50 text-violet-700"
                          : "border-slate-200 bg-white text-slate-600 hover:border-violet-200"
                      }`}
                      key={item}
                      onClick={() =>
                        setMaterials((current) =>
                          selected ? current.filter((value) => value !== item) : [...current, item],
                        )
                      }
                      type="button"
                    >
                      {formatLabel(item)}
                    </button>
                  );
                })}
              </div>
            </div>
            <label className="mt-5 block space-y-2 text-sm font-medium text-slate-700">
              Design notes
              <textarea
                className="min-h-28 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-violet-300 focus:ring-4 focus:ring-violet-100"
                maxLength={1500}
                onChange={(event) => setInstructions(event.target.value)}
                placeholder="Example: emphasize vertical fins and warm wood accents."
                value={instructions}
              />
            </label>
            {actions.generate.isError ? (
              <div className="mt-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {actions.generate.error instanceof Error
                  ? actions.generate.error.message
                  : "Exterior generation failed safely."}
              </div>
            ) : null}
            <div className="mt-5 flex justify-end">
              <Button disabled={!ready || actions.generate.isPending} onClick={() => void generate()}>
                <Sparkles aria-hidden="true" />
                {actions.generate.isPending ? "Generating" : "Generate conceptual elevation"}
              </Button>
            </div>
          </Panel>
        </div>

        <aside className="space-y-6">
          <Panel className="p-5">
            <SectionHeader title="Latest runs" />
            {runs.isLoading ? <Skeleton className="mt-4 h-28 w-full" /> : null}
            {runs.data?.length ? (
              <div className="mt-4 space-y-3">
                {runs.data.slice(0, 5).map((run) => (
                  <div className="rounded-2xl border border-slate-200 bg-white p-4" key={run.id}>
                    <p className="text-sm font-medium text-slate-900">{formatLabel(run.status)}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      {formatLabel(run.style)} · {run.completedOptionCount}/{run.requestedOptionCount} options
                    </p>
                    {run.safeFailureMessage ? (
                      <p className="mt-2 text-xs text-red-600">{run.safeFailureMessage}</p>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-4 text-sm text-slate-500">No exterior runs yet.</p>
            )}
          </Panel>
          <Panel className="p-5">
            <SectionHeader title="Generated assets" />
            {options.data?.length ? (
              <div className="mt-4 space-y-3">
                {options.data.slice(0, 4).map((option) => (
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4" key={option.id}>
                    <div className="flex items-center gap-2 text-sm font-medium text-slate-900">
                      <ImageIcon aria-hidden="true" className="size-4 text-violet-600" />
                      {option.title}
                    </div>
                    <p className="mt-2 text-xs text-slate-500">{option.disclaimer}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-4 text-sm text-slate-500">Generated options will appear here.</p>
            )}
          </Panel>
        </aside>
      </div>
    </div>
  );
}

function ReadinessPill({ ok, title }: { ok: boolean; title: string }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
      <CheckCircle2 aria-hidden="true" className={`size-5 ${ok ? "text-emerald-600" : "text-slate-300"}`} />
      <span className="text-sm font-medium text-slate-700">{title}</span>
    </div>
  );
}

function ExteriorSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-44 w-full rounded-[2rem]" />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Skeleton className="h-96 w-full" />
        <Skeleton className="h-96 w-full" />
      </div>
    </div>
  );
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}
