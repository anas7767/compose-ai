"use client";

import { useAuth } from "@clerk/nextjs";
import type {
  FloorPlanComparison,
  FloorPlanDesignVersion,
  FloorPlanFailureBudget,
  FloorPlanGenerationRequest,
  FloorPlanOption,
  FloorPlanRun,
  FloorPlanReadiness,
  ProjectDetail,
} from "@compose-ai/shared";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  Bath,
  BedDouble,
  Building2,
  Car,
  Check,
  CheckCircle2,
  CircleStop,
  Clock3,
  GitCompareArrows,
  History,
  Layers3,
  LayoutGrid,
  ListChecks,
  LoaderCircle,
  Play,
  RotateCcw,
  Ruler,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  X,
  XCircle,
} from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import Link from "next/link";
import * as React from "react";

import { FloorPlanOptionCard } from "@/components/floor-plans/floor-plan-option-card";
import { FloorPlanPreview } from "@/components/floor-plans/floor-plan-preview";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/ui/panel";
import { Progress } from "@/components/ui/progress";
import { SectionHeader } from "@/components/ui/section-header";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  requireFloorPlanToken,
  useFloorPlanDesignVersions,
  useFloorPlanOptions,
  useFloorPlanReadiness,
  useFloorPlanRun,
  useFloorPlanRuns,
} from "@/hooks/use-floor-plans";
import { useProjectDetail } from "@/hooks/use-projects";
import {
  acceptFloorPlanOption,
  cancelFloorPlanRun,
  compareFloorPlanOptions,
  createFloorPlanRun,
  deleteFloorPlanDesignVersion,
  rejectFloorPlanOption,
  restoreFloorPlanDesignVersion,
  retryFloorPlanRun,
  streamFloorPlanRun,
  validateFloorPlanOption,
} from "@/lib/api/floor-plans";
import { cn } from "@/lib/utils";

interface FloorPlanGeneratorPageProps {
  projectId: string;
}

const defaultFailureBudget: FloorPlanFailureBudget = {
  maxSolverAttempts: 20,
  maxProviderRetries: 2,
  maxProcessingSeconds: 180,
  maxInvalidCandidates: 12,
};

const terminalStatuses = new Set(["completed", "partial", "failed", "cancelled"]);

export function FloorPlanGeneratorPage({ projectId }: FloorPlanGeneratorPageProps) {
  const { getToken } = useAuth();
  const queryClient = useQueryClient();
  const reducedMotion = useReducedMotion();
  const project = useProjectDetail(projectId);
  const readiness = useFloorPlanReadiness(projectId);
  const runs = useFloorPlanRuns(projectId);
  const designs = useFloorPlanDesignVersions(projectId);
  const [activeRunId, setActiveRunId] = React.useState<string | null>(null);
  const run = useFloorPlanRun(projectId, activeRunId);
  const options = useFloorPlanOptions(projectId, activeRunId);
  const [selectedOptionId, setSelectedOptionId] = React.useState<string | null>(null);
  const [compareIds, setCompareIds] = React.useState<Set<string>>(new Set());
  const [comparison, setComparison] = React.useState<FloorPlanComparison | null>(null);
  const [previewFloor, setPreviewFloor] = React.useState(0);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [confirmAccept, setConfirmAccept] = React.useState(false);
  const [rejecting, setRejecting] = React.useState(false);
  const [rejectionReason, setRejectionReason] = React.useState("");
  const [seed, setSeed] = React.useState("");
  const [mobileView, setMobileView] = React.useState<"inputs" | "options" | "review">(
    "inputs",
  );
  const [request, setRequest] = React.useState<FloorPlanGenerationRequest>({
    optionCount: 3,
    deterministicSeed: null,
    preferredStyle: null,
    budgetMode: "balanced",
    vastuPreference: "not_required",
    userConstraints: [],
    diversityThreshold: 0.25,
    failureBudget: defaultFailureBudget,
  });
  const streamController = React.useRef<AbortController | null>(null);
  const preferencesInitialized = React.useRef(false);

  React.useEffect(() => {
    if (!project.data || preferencesInitialized.current) return;
    preferencesInitialized.current = true;
    setRequest((current) => ({
      ...current,
      preferredStyle: project.data?.requirements.preferredStyle ?? null,
      vastuPreference: project.data?.requirements.vastuPreference ?? "not_required",
    }));
  }, [project.data]);

  React.useEffect(() => {
    if (activeRunId || !runs.data?.length) return;
    const active = runs.data.find((item) => !terminalStatuses.has(item.status));
    setActiveRunId((active ?? runs.data[0]).id);
  }, [activeRunId, runs.data]);

  React.useEffect(() => {
    const available = options.data ?? [];
    if (!available.length) {
      setSelectedOptionId(null);
      return;
    }
    if (!selectedOptionId || !available.some((item) => item.id === selectedOptionId)) {
      setSelectedOptionId(available[0].id);
      setPreviewFloor(0);
    }
  }, [options.data, selectedOptionId]);

  React.useEffect(() => {
    if (!activeRunId) return;
    const controller = new AbortController();
    streamController.current?.abort();
    streamController.current = controller;
    void (async () => {
      try {
        const token = await requireFloorPlanToken(getToken);
        await streamFloorPlanRun(
          token,
          projectId,
          activeRunId,
          (event) => {
            if (event.eventType === "option.completed") {
              void queryClient.invalidateQueries({
                queryKey: ["floor-plans", projectId, "runs", activeRunId, "options"],
              });
            }
            if (["run.completed", "run.partial", "run.failed", "run.cancelled"].includes(event.eventType)) {
              void Promise.all([
                queryClient.invalidateQueries({
                  queryKey: ["floor-plans", projectId, "runs", activeRunId],
                }),
                queryClient.invalidateQueries({
                  queryKey: ["floor-plans", projectId, "runs", activeRunId, "options"],
                }),
                queryClient.invalidateQueries({ queryKey: ["floor-plans", projectId, "runs"] }),
              ]);
            }
          },
          controller.signal,
        );
      } catch (streamError) {
        if (!(streamError instanceof DOMException && streamError.name === "AbortError")) {
          setError(
            streamError instanceof Error
              ? streamError.message
              : "Generation progress could not be streamed.",
          );
        }
      }
    })();
    return () => controller.abort();
  }, [activeRunId, getToken, projectId, queryClient]);

  const selectedOption = React.useMemo(
    () => options.data?.find((item) => item.id === selectedOptionId) ?? null,
    [options.data, selectedOptionId],
  );
  const isGenerating = Boolean(run.data && !terminalStatuses.has(run.data.status));
  const archived = project.data?.status === "archived";

  const startGeneration = React.useCallback(async () => {
    if (!readiness.data?.ready || archived || busy) return;
    setBusy(true);
    setError(null);
    setComparison(null);
    setCompareIds(new Set());
    try {
      const parsedSeed = seed.trim() ? Number(seed) : null;
      if (parsedSeed !== null && (!Number.isSafeInteger(parsedSeed) || parsedSeed < 0)) {
        throw new Error("Seed must be a positive whole number within the supported range.");
      }
      const accepted = await createFloorPlanRun(
        await requireFloorPlanToken(getToken),
        projectId,
        { ...request, deterministicSeed: parsedSeed },
        crypto.randomUUID(),
      );
      setActiveRunId(accepted.run.id);
      setSelectedOptionId(null);
      setMobileView("options");
      queryClient.setQueryData(
        ["floor-plans", projectId, "runs", accepted.run.id],
        accepted.run,
      );
      await queryClient.invalidateQueries({ queryKey: ["floor-plans", projectId, "runs"] });
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Generation could not start.");
    } finally {
      setBusy(false);
    }
  }, [archived, busy, getToken, projectId, queryClient, readiness.data?.ready, request, seed]);

  const stopGeneration = React.useCallback(async () => {
    if (!activeRunId) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await cancelFloorPlanRun(
        await requireFloorPlanToken(getToken),
        projectId,
        activeRunId,
      );
      queryClient.setQueryData(["floor-plans", projectId, "runs", activeRunId], updated);
      streamController.current?.abort();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Generation could not stop.");
    } finally {
      setBusy(false);
    }
  }, [activeRunId, getToken, projectId, queryClient]);

  const retryGeneration = React.useCallback(async () => {
    if (!activeRunId || busy) return;
    setBusy(true);
    setError(null);
    try {
      const accepted = await retryFloorPlanRun(
        await requireFloorPlanToken(getToken),
        projectId,
        activeRunId,
        crypto.randomUUID(),
      );
      setActiveRunId(accepted.run.id);
      setSelectedOptionId(null);
      await queryClient.invalidateQueries({ queryKey: ["floor-plans", projectId, "runs"] });
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Generation could not retry.");
    } finally {
      setBusy(false);
    }
  }, [activeRunId, busy, getToken, projectId, queryClient]);

  const compare = React.useCallback(async () => {
    if (compareIds.size < 2) return;
    setBusy(true);
    setError(null);
    try {
      setComparison(
        await compareFloorPlanOptions(
          await requireFloorPlanToken(getToken),
          projectId,
          [...compareIds],
        ),
      );
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Options could not be compared.");
    } finally {
      setBusy(false);
    }
  }, [busy, compareIds, getToken, projectId]);

  const accept = React.useCallback(async () => {
    if (!selectedOption) return;
    setBusy(true);
    setError(null);
    try {
      await acceptFloorPlanOption(
        await requireFloorPlanToken(getToken),
        projectId,
        selectedOption,
      );
      setConfirmAccept(false);
      await Promise.all([
        options.refetch(),
        queryClient.invalidateQueries({
          queryKey: ["floor-plans", projectId, "design-versions"],
        }),
      ]);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Option could not be accepted.");
    } finally {
      setBusy(false);
    }
  }, [getToken, options, projectId, queryClient, selectedOption]);

  const reject = React.useCallback(async () => {
    if (!selectedOption || rejectionReason.trim().length < 4) return;
    setBusy(true);
    setError(null);
    try {
      await rejectFloorPlanOption(
        await requireFloorPlanToken(getToken),
        projectId,
        selectedOption,
        rejectionReason.trim(),
      );
      setRejecting(false);
      setRejectionReason("");
      await options.refetch();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Option could not be rejected.");
    } finally {
      setBusy(false);
    }
  }, [getToken, options, projectId, rejectionReason, selectedOption]);

  const validateSelectedOption = React.useCallback(async () => {
    if (!selectedOption || busy) return;
    setBusy(true);
    setError(null);
    try {
      await validateFloorPlanOption(
        await requireFloorPlanToken(getToken),
        projectId,
        selectedOption.id,
      );
      await options.refetch();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Option validation failed.");
    } finally {
      setBusy(false);
    }
  }, [busy, getToken, options, projectId, selectedOption]);

  const restoreDesign = React.useCallback(
    async (design: FloorPlanDesignVersion) => {
      if (busy) return;
      setBusy(true);
      setError(null);
      try {
        await restoreFloorPlanDesignVersion(
          await requireFloorPlanToken(getToken),
          projectId,
          design.id,
          `Restored ${design.name}`,
        );
        await queryClient.invalidateQueries({
          queryKey: ["floor-plans", projectId, "design-versions"],
        });
      } catch (actionError) {
        setError(
          actionError instanceof Error ? actionError.message : "Design version could not be restored.",
        );
      } finally {
        setBusy(false);
      }
    },
    [busy, getToken, projectId, queryClient],
  );

  const deleteDesign = React.useCallback(
    async (design: FloorPlanDesignVersion) => {
      if (busy) return;
      setBusy(true);
      setError(null);
      try {
        await deleteFloorPlanDesignVersion(
          await requireFloorPlanToken(getToken),
          projectId,
          design.id,
        );
        await queryClient.invalidateQueries({
          queryKey: ["floor-plans", projectId, "design-versions"],
        });
      } catch (actionError) {
        setError(
          actionError instanceof Error ? actionError.message : "Design version could not be hidden.",
        );
      } finally {
        setBusy(false);
      }
    },
    [busy, getToken, projectId, queryClient],
  );

  if (project.isLoading || readiness.isLoading) return <FloorPlanPageSkeleton />;
  if (project.isError || !project.data || readiness.isError || !readiness.data) {
    return (
      <div className="compose-floor-plan-light -mx-4 -my-6 flex min-h-[calc(100dvh-4rem)] items-center justify-center px-4 sm:-mx-6 sm:px-6 lg:-mx-8 lg:-my-8 lg:px-8">
        <EmptyState
          action={
            <Button
              className="compose-floor-action"
              onClick={() => void Promise.all([project.refetch(), readiness.refetch()])}
            >
              Retry
            </Button>
          }
          className="w-full max-w-xl rounded-lg border border-slate-200 bg-white shadow-sm"
          description="Compose could not load the project and plot context needed for floor-plan generation."
          icon={Layers3}
          title="Floor Plan Generator unavailable"
        />
      </div>
    );
  }

  return (
    <div className="compose-floor-plan-light -mx-4 -my-6 min-h-[calc(100dvh-4rem)] space-y-5 bg-[#f7f8fb] px-4 py-5 sm:-mx-6 sm:px-6 lg:-mx-8 lg:-my-8 lg:px-6 lg:py-6">
      <header className="mx-auto flex w-full max-w-[1540px] flex-col gap-4 border-b border-slate-200 pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <Button asChild className="-ml-3 text-slate-500" size="sm" variant="ghost">
            <Link href={`/projects/${projectId}`}>
              <ArrowLeft aria-hidden="true" />
              Project
            </Link>
          </Button>
          <div className="mt-2 flex items-center gap-3">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-md border border-violet-200 bg-white text-violet-700 shadow-sm">
              <LayoutGrid aria-hidden="true" className="size-[18px]" />
            </span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2.5">
                <h1 className="text-xl font-semibold text-slate-950">AI Floor Plan Generator</h1>
                <Badge className="rounded-md border-amber-200 bg-amber-50 text-amber-700" variant="warning">
                  Conceptual Design - Not for Construction
                </Badge>
              </div>
              <p className="mt-0.5 truncate text-sm text-slate-500">{project.data.name}</p>
            </div>
          </div>
        </div>
        {runs.data?.length ? (
          <label className="w-full text-xs font-medium text-slate-500 lg:w-72">
            Generation history
            <Select
              className="mt-2 bg-white"
              onChange={(event) => {
                setActiveRunId(event.target.value);
                setComparison(null);
                setCompareIds(new Set());
              }}
              value={activeRunId ?? ""}
            >
              {runs.data.map((item) => (
                <option key={item.id} value={item.id}>
                  {new Date(item.createdAt).toLocaleString()} | {formatLabel(item.status)}
                </option>
              ))}
            </Select>
          </label>
        ) : null}
      </header>

      <div className="mx-auto w-full max-w-[1540px]">
        <WorkflowSteps
          designCount={designs.data?.length ?? 0}
          optionCount={options.data?.length ?? 0}
          readinessReady={readiness.data.ready}
          run={run.data ?? null}
        />
      </div>

      <MobileWorkspaceNav
        onChange={setMobileView}
        optionCount={options.data?.length ?? 0}
        value={mobileView}
      />

      <AnimatePresence initial={false}>
        {error ? (
          <motion.div
            animate={{ opacity: 1, y: 0 }}
            className="mx-auto flex w-full max-w-[1540px] items-start gap-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-700"
            exit={reducedMotion ? undefined : { opacity: 0, y: -4 }}
            initial={reducedMotion ? false : { opacity: 0, y: -4 }}
            role="alert"
          >
            <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            <p className="min-w-0 flex-1 leading-5">{error}</p>
            <button
              aria-label="Dismiss error"
              className="flex size-7 shrink-0 items-center justify-center rounded-md text-rose-600 outline-none transition-colors hover:bg-rose-100 focus-visible:ring-2 focus-visible:ring-rose-400"
              onClick={() => setError(null)}
              type="button"
            >
              <X aria-hidden="true" className="size-3.5" />
            </button>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <div className="mx-auto grid w-full max-w-[1540px] gap-4 xl:grid-cols-[330px_minmax(0,1fr)]">
        <aside
          className={cn("space-y-4", mobileView !== "inputs" && "hidden", "xl:block")}
        >
          <ReadinessPanel project={project.data} readiness={readiness.data} />
          <GenerationSettings
            archived={archived}
            busy={busy}
            canGenerate={readiness.data.ready && !isGenerating}
            onGenerate={() => void startGeneration()}
            onRequestChange={setRequest}
            onSeedChange={setSeed}
            request={request}
            seed={seed}
          />
          <DesignVersionsPanel
            busy={busy}
            designs={designs.data ?? []}
            onDelete={(design) => void deleteDesign(design)}
            onRestore={(design) => void restoreDesign(design)}
          />
        </aside>

        <main className="min-w-0 space-y-4">
          {run.data ? (
            <div className={cn(mobileView !== "options" && "hidden", "xl:block")}>
              <RunStatusPanel
                busy={busy}
                onCancel={() => void stopGeneration()}
                onRetry={() => void retryGeneration()}
                run={run.data}
              />
            </div>
          ) : null}

          {run.isError ? (
            <div className={cn(mobileView !== "options" && "hidden", "xl:block")}>
              <InlineError
                description="Compose could not load the selected generation run."
                onRetry={() => void run.refetch()}
                title="Generation status unavailable"
              />
            </div>
          ) : null}

          <section
            aria-labelledby="floor-plan-options-title"
            className={cn(
              "space-y-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:p-5",
              mobileView !== "options" && "hidden",
              "xl:block",
            )}
          >
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase text-violet-700">Step 2</p>
                <h2 className="mt-1 text-base font-semibold text-slate-950" id="floor-plan-options-title">
                  Explore generated options
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  {options.data?.length ?? 0} validated topology option{options.data?.length === 1 ? "" : "s"}
                </p>
              </div>
              <Button
                className="compose-floor-action bg-white"
                disabled={compareIds.size < 2 || busy}
                onClick={() => void compare()}
                size="sm"
                variant="outline"
              >
                <GitCompareArrows aria-hidden="true" />
                Compare {compareIds.size ? `(${compareIds.size})` : ""}
              </Button>
            </div>

            {options.isLoading ? (
              <OptionGallerySkeleton />
            ) : null}
            {options.isError ? (
              <InlineError
                description="The generated options could not be loaded. Your run and saved versions are unchanged."
                onRetry={() => void options.refetch()}
                title="Options unavailable"
              />
            ) : null}
            {!options.isLoading && options.data?.length ? (
              <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
                {options.data.map((option, index) => (
                  <FloorPlanOptionCard
                    compareSelected={compareIds.has(option.id)}
                    index={index}
                    key={option.id}
                    onCompareChange={(checked) =>
                      setCompareIds((current) => {
                        const next = new Set(current);
                        if (checked && next.size < 5) next.add(option.id);
                        if (!checked) next.delete(option.id);
                        return next;
                      })
                    }
                    onSelect={() => {
                      setSelectedOptionId(option.id);
                      setPreviewFloor(0);
                      setMobileView("review");
                    }}
                    option={option}
                    selected={selectedOptionId === option.id}
                  />
                ))}
              </div>
            ) : null}
            {!options.isLoading && !options.data?.length ? (
              <div className="border-t border-slate-200 pt-2">
                <EmptyState
                  description={
                    isGenerating
                      ? "Validated options will appear here as Compose completes each topology."
                      : readiness.data.ready
                        ? "Review your inputs, then generate three to five distinct conceptual layouts."
                        : "Complete the blocking project inputs before starting generation."
                  }
                  icon={Layers3}
                  title={isGenerating ? "Generation is in progress" : "Ready for your first options"}
                />
              </div>
            ) : null}
          </section>

          {comparison ? (
            <div className={cn(mobileView !== "options" && "hidden", "xl:block")}>
              <ComparisonPanel comparison={comparison} onClose={() => setComparison(null)} />
            </div>
          ) : null}

          {selectedOption ? (
            <section
              aria-labelledby="selected-option-title"
              className={cn(
                "grid gap-4 2xl:grid-cols-[minmax(0,1fr)_360px]",
                mobileView !== "review" && "hidden",
                "xl:grid",
              )}
            >
              <Panel className="overflow-hidden border-slate-200 bg-white shadow-sm">
                <div className="border-b border-slate-200 px-4 py-4 sm:px-5">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold uppercase text-violet-700">Step 3 - Review</p>
                      <h2 className="mt-1 text-base font-semibold text-slate-950" id="selected-option-title">
                        {selectedOption.title}
                      </h2>
                      <p className="mt-1 text-xs text-slate-500">
                        Geometry {selectedOption.geometryHash.slice(0, 12)} | Seed {selectedOption.deterministicSeed}
                      </p>
                    </div>
                    <Badge className="rounded-md" variant="success">Validated geometry</Badge>
                  </div>
                </div>
                <FloorPlanPreview
                  floorIndex={previewFloor}
                  geometry={selectedOption.geometry}
                  onFloorChange={setPreviewFloor}
                />
              </Panel>
              <OptionInspector
                busy={busy}
                canRegenerate={readiness.data.ready && !isGenerating && !archived}
                onAccept={() => setConfirmAccept(true)}
                onReject={() => setRejecting((current) => !current)}
                onRejectConfirm={() => void reject()}
                onRegenerate={() => void startGeneration()}
                onRejectionReasonChange={setRejectionReason}
                onValidate={() => void validateSelectedOption()}
                option={selectedOption}
                rejecting={rejecting}
                rejectionReason={rejectionReason}
              />
            </section>
          ) : (
            <div className={cn(mobileView !== "review" && "hidden", "xl:block")}>
              <ReviewEmptyState onOpenOptions={() => setMobileView("options")} />
            </div>
          )}
        </main>
      </div>

      <ConfirmDialog
        confirmLabel="Create design version"
        description="This creates an immutable conceptual design version from the selected validated geometry. It is not construction documentation or professional approval."
        onConfirm={() => void accept()}
        onOpenChange={setConfirmAccept}
        open={confirmAccept}
        pending={busy}
        title="Accept conceptual option?"
      />
    </div>
  );
}

type WorkflowStepState = "complete" | "active" | "upcoming";

function WorkflowSteps({
  designCount,
  optionCount,
  readinessReady,
  run,
}: {
  designCount: number;
  optionCount: number;
  readinessReady: boolean;
  run: FloorPlanRun | null;
}) {
  const reducedMotion = useReducedMotion();
  const steps: Array<{
    description: string;
    icon: typeof ListChecks;
    label: string;
    state: WorkflowStepState;
  }> = [
    {
      description: readinessReady ? "Sources validated" : "Complete required inputs",
      icon: ListChecks,
      label: "Review inputs",
      state: readinessReady ? "complete" : "active",
    },
    {
      description: optionCount
        ? `${optionCount} validated option${optionCount === 1 ? "" : "s"}`
        : run
          ? formatLabel(run.status)
          : "Choose generation settings",
      icon: Sparkles,
      label: "Generate options",
      state: optionCount ? "complete" : readinessReady ? "active" : "upcoming",
    },
    {
      description: designCount
        ? `${designCount} saved design version${designCount === 1 ? "" : "s"}`
        : optionCount
          ? "Compare and approve"
          : "Waiting for options",
      icon: LayoutGrid,
      label: "Review design",
      state: designCount ? "complete" : optionCount ? "active" : "upcoming",
    },
  ];

  return (
    <ol
      aria-label="Floor-plan generation workflow"
      className="grid overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm sm:grid-cols-3"
    >
      {steps.map((step, index) => {
        const Icon = step.icon;
        return (
          <li
            aria-current={step.state === "active" ? "step" : undefined}
            className={cn(
              "relative flex min-h-20 items-center gap-3 border-slate-200 px-4 py-3 sm:border-l sm:first:border-l-0",
              index > 0 && "border-t sm:border-t-0",
              step.state === "active" && "bg-violet-50/65",
            )}
            key={step.label}
          >
            <span
              className={cn(
                "relative flex size-9 shrink-0 items-center justify-center rounded-md border",
                step.state === "complete" && "border-emerald-200 bg-emerald-50 text-emerald-700",
                step.state === "active" && "border-violet-200 bg-white text-violet-700 shadow-sm",
                step.state === "upcoming" && "border-slate-200 bg-slate-50 text-slate-400",
              )}
            >
              {step.state === "complete" ? (
                <Check aria-hidden="true" className="size-4" />
              ) : (
                <Icon aria-hidden="true" className="size-4" />
              )}
              {step.state === "active" ? (
                <motion.span
                  animate={reducedMotion ? undefined : { opacity: [0.35, 1, 0.35] }}
                  className="absolute -right-1 -top-1 size-2 rounded-full bg-violet-600"
                  transition={{ duration: 1.8, ease: "easeInOut", repeat: Infinity }}
                />
              ) : null}
            </span>
            <span className="min-w-0">
              <span className="block text-sm font-semibold text-slate-900">
                {index + 1}. {step.label}
              </span>
              <span className="mt-0.5 block truncate text-xs text-slate-500">
                {step.description}
              </span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function MobileWorkspaceNav({
  onChange,
  optionCount,
  value,
}: {
  onChange: (value: "inputs" | "options" | "review") => void;
  optionCount: number;
  value: "inputs" | "options" | "review";
}) {
  const items = [
    { icon: SlidersHorizontal, label: "Inputs", value: "inputs" as const },
    { icon: LayoutGrid, label: `Options${optionCount ? ` (${optionCount})` : ""}`, value: "options" as const },
    { icon: ListChecks, label: "Review", value: "review" as const },
  ];
  return (
    <div
      aria-label="Floor-plan workspace"
      className="mx-auto grid w-full max-w-[1540px] grid-cols-3 rounded-lg border border-slate-200 bg-white p-1 shadow-sm xl:hidden"
      role="tablist"
    >
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <button
            aria-selected={value === item.value}
            className={cn(
              "flex h-10 min-w-0 items-center justify-center gap-1.5 rounded-md px-2 text-xs font-medium text-slate-500 outline-none transition-colors hover:text-slate-900 focus-visible:ring-2 focus-visible:ring-violet-500",
              value === item.value && "bg-violet-50 text-violet-700 shadow-sm",
            )}
            key={item.value}
            onClick={() => onChange(item.value)}
            role="tab"
            type="button"
          >
            <Icon aria-hidden="true" className="size-3.5 shrink-0" />
            <span className="truncate">{item.label}</span>
          </button>
        );
      })}
    </div>
  );
}

function ReadinessPanel({
  project,
  readiness,
}: {
  project: ProjectDetail;
  readiness: FloorPlanReadiness;
}) {
  return (
    <Panel className="overflow-hidden border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 px-5 py-4">
        <SectionHeader
          action={
            <Badge className="rounded-md" variant={readiness.ready ? "success" : "warning"}>
              {readiness.ready ? "Ready" : "Action required"}
            </Badge>
          }
          title="Input summary"
        />
        <p className="mt-1 text-xs leading-5 text-slate-500">
          Approved project sources used by the geometry engine.
        </p>
      </div>

      <dl className="grid grid-cols-2 border-b border-slate-200">
        <InputFact icon={Building2} label="Floors" value={project.requirements.floors} />
        <InputFact icon={BedDouble} label="Bedrooms" value={project.requirements.bedrooms} />
        <InputFact icon={Bath} label="Bathrooms" value={project.requirements.bathrooms} />
        <InputFact icon={Car} label="Parking" value={project.requirements.parkingSpaces} />
      </dl>

      <dl className="px-5 py-2 text-sm">
        <SourceRow label="Project version" value={`v${readiness.projectVersion}`} />
        <SourceRow
          label="Approved brief"
          value={readiness.approvedBriefVersion ? `v${readiness.approvedBriefVersion}` : null}
        />
        <SourceRow label="Plot boundary" value={readiness.boundaryVersionId ? "Validated" : null} />
        <SourceRow
          label="Buildable area"
          value={formatArea(readiness.buildableAreaM2)}
        />
        <SourceRow label="Preferred style" value={project.requirements.preferredStyle} />
      </dl>
      {readiness.issues.length ? (
        <ul className="space-y-2 border-t border-slate-200 px-5 py-4">
          {readiness.issues.map((issue) => (
            <li
              className={cn(
                "flex gap-3 rounded-md border px-3 py-2 text-xs leading-5",
                issue.severity === "blocking"
                  ? "border-rose-200 bg-rose-50 text-rose-700"
                  : "border-amber-200 bg-amber-50 text-amber-700",
              )}
              key={issue.code}
            >
              <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              <span>
                {issue.message}{" "}
                {issue.actionUrl ? (
                  <Link className="font-semibold underline underline-offset-4" href={issue.actionUrl}>
                    Open
                  </Link>
                ) : null}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </Panel>
  );
}

function InputFact({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Building2;
  label: string;
  value: number;
}) {
  return (
    <div className="flex min-h-16 items-center gap-2.5 border-l border-t border-slate-200 px-4 py-3 first:border-l-0 [&:nth-child(-n+2)]:border-t-0 [&:nth-child(3)]:border-l-0">
      <Icon aria-hidden="true" className="size-4 shrink-0 text-violet-600" />
      <div>
        <dt className="text-[11px] font-medium text-slate-500">{label}</dt>
        <dd className="mt-0.5 text-sm font-semibold tabular-nums text-slate-900">{value}</dd>
      </div>
    </div>
  );
}

function GenerationSettings({
  archived,
  busy,
  canGenerate,
  onGenerate,
  onRequestChange,
  onSeedChange,
  request,
  seed,
}: {
  archived: boolean;
  busy: boolean;
  canGenerate: boolean;
  onGenerate: () => void;
  onRequestChange: (request: FloorPlanGenerationRequest) => void;
  onSeedChange: (seed: string) => void;
  request: FloorPlanGenerationRequest;
  seed: string;
}) {
  const updateBudget = (key: keyof FloorPlanFailureBudget, value: number) =>
    onRequestChange({
      ...request,
      failureBudget: { ...request.failureBudget, [key]: value },
    });
  return (
    <Panel className="border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-xs font-semibold uppercase text-violet-700">Step 1</p>
      <SectionHeader className="mt-1" title="Generation settings" />
      <p className="mt-1 text-xs leading-5 text-slate-500">
        Tune the run without changing your approved project brief.
      </p>
      <div className="mt-5 space-y-5">
        <fieldset>
          <legend className="text-sm font-medium text-slate-800">Number of options</legend>
          <div className="mt-2 grid grid-cols-3 gap-1 rounded-md border border-slate-200 bg-slate-50 p-1">
            {[3, 4, 5].map((count) => (
              <button
                aria-pressed={request.optionCount === count}
                className={cn(
                  "h-9 rounded-md text-sm font-medium text-slate-500 outline-none transition-colors hover:text-slate-900 focus-visible:ring-2 focus-visible:ring-violet-500",
                  request.optionCount === count && "bg-white text-violet-700 shadow-sm",
                )}
                key={count}
                onClick={() => onRequestChange({ ...request, optionCount: count })}
                type="button"
              >
                {count}
              </button>
            ))}
          </div>
        </fieldset>
        <FormField htmlFor="floor-plan-style" label="Preferred style">
          <Input
            id="floor-plan-style"
            maxLength={80}
            onChange={(event) =>
              onRequestChange({ ...request, preferredStyle: event.target.value || null })
            }
            placeholder="Project brief default"
            value={request.preferredStyle ?? ""}
          />
        </FormField>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
          <FormField htmlFor="floor-plan-budget" label="Budget mode">
            <Select
              id="floor-plan-budget"
              onChange={(event) =>
                onRequestChange({
                  ...request,
                  budgetMode: event.target.value as FloorPlanGenerationRequest["budgetMode"],
                })
              }
              value={request.budgetMode}
            >
              <option value="economy">Economy</option>
              <option value="balanced">Balanced</option>
              <option value="premium">Premium</option>
            </Select>
          </FormField>
          <FormField htmlFor="floor-plan-vastu" label="Vastu preference">
            <Select
              id="floor-plan-vastu"
              onChange={(event) =>
                onRequestChange({
                  ...request,
                  vastuPreference: event.target
                    .value as FloorPlanGenerationRequest["vastuPreference"],
                })
              }
              value={request.vastuPreference}
            >
              <option value="not_required">Not required</option>
              <option value="preferred">Preferred</option>
              <option value="strict">Strict preference</option>
            </Select>
          </FormField>
        </div>
        <FormField htmlFor="floor-plan-seed" label="Deterministic seed">
          <Input
            id="floor-plan-seed"
            inputMode="numeric"
            min={0}
            onChange={(event) => onSeedChange(event.target.value.replace(/\D/g, ""))}
            placeholder="Automatic"
            type="text"
            value={seed}
          />
        </FormField>
        <FormField htmlFor="floor-plan-diversity" label="Topology diversity">
          <div className="flex items-center gap-3">
            <input
              aria-label="Minimum topology diversity"
              className="h-2 min-w-0 flex-1 cursor-pointer accent-[var(--primary)]"
              id="floor-plan-diversity"
              max="0.6"
              min="0.15"
              onChange={(event) =>
                onRequestChange({ ...request, diversityThreshold: Number(event.target.value) })
              }
              step="0.05"
              type="range"
              value={request.diversityThreshold}
            />
            <span className="w-10 text-right text-sm tabular-nums">
              {Math.round(request.diversityThreshold * 100)}%
            </span>
          </div>
        </FormField>
        <details className="border-t border-slate-200 pt-4">
          <summary className="cursor-pointer text-sm font-medium text-slate-800 outline-none focus-visible:ring-2 focus-visible:ring-violet-500">
            Failure budget
          </summary>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <BudgetInput
              label="Solver attempts"
              max={100}
              min={1}
              onChange={(value) => updateBudget("maxSolverAttempts", value)}
              value={request.failureBudget.maxSolverAttempts}
            />
            <BudgetInput
              label="Provider retries"
              max={10}
              min={0}
              onChange={(value) => updateBudget("maxProviderRetries", value)}
              value={request.failureBudget.maxProviderRetries}
            />
            <BudgetInput
              label="Time limit (seconds)"
              max={1800}
              min={10}
              onChange={(value) => updateBudget("maxProcessingSeconds", value)}
              value={request.failureBudget.maxProcessingSeconds}
            />
            <BudgetInput
              label="Invalid candidates"
              max={100}
              min={1}
              onChange={(value) => updateBudget("maxInvalidCandidates", value)}
              value={request.failureBudget.maxInvalidCandidates}
            />
          </div>
        </details>
        <Button
          className="compose-floor-action w-full shadow-sm"
          disabled={!canGenerate || busy || archived}
          onClick={onGenerate}
          type="button"
        >
          {busy ? <LoaderCircle aria-hidden="true" className="animate-spin" /> : <Play aria-hidden="true" />}
          Generate options
        </Button>
        {archived ? (
          <p className="text-xs leading-5 text-amber-700">
            Archived projects are read-only. Restore this project before generating options.
          </p>
        ) : null}
      </div>
    </Panel>
  );
}

function RunStatusPanel({
  busy,
  onCancel,
  onRetry,
  run,
}: {
  busy: boolean;
  onCancel: () => void;
  onRetry: () => void;
  run: FloorPlanRun;
}) {
  const reducedMotion = useReducedMotion();
  const active = !terminalStatuses.has(run.status);
  const statusVariant =
    run.status === "completed"
      ? "success"
      : run.status === "failed" || run.status === "partial"
        ? "warning"
        : "neutral";
  const stages = [
    { keys: ["queued", "preflighting"], label: "Prepare" },
    { keys: ["building_context"], label: "Context" },
    { keys: ["generating"], label: "Generate" },
    { keys: ["solving"], label: "Solve" },
    { keys: ["validating"], label: "Validate" },
    { keys: ["completed", "partial"], label: "Complete" },
  ];
  const matchedIndex = stages.findIndex((stage) => stage.keys.includes(run.status));
  const currentIndex = matchedIndex >= 0
    ? matchedIndex
    : Math.min(4, Math.max(0, Math.floor(run.progressPercent / 20)));
  const runComplete = run.status === "completed" || run.status === "partial";
  return (
    <Panel className="overflow-hidden border-slate-200 bg-white shadow-sm" aria-live="polite">
      <div className="p-5 sm:p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge className="rounded-md" variant={statusVariant}>{formatLabel(run.status)}</Badge>
            {run.cacheHit ? <Badge className="rounded-md" variant="outline">Cached result</Badge> : null}
          </div>
          <h2 className="mt-3 text-base font-semibold text-slate-950">
            {active ? "Compose is developing your layouts" : "Generation run"}
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            {run.completedOptionCount} of {run.requestedOptionCount} options | Seed {run.deterministicSeed}
          </p>
        </div>
        <div className="flex gap-2">
          {active ? (
            <Button disabled={busy} onClick={onCancel} size="sm" variant="outline">
              <CircleStop aria-hidden="true" />
              Stop
            </Button>
          ) : null}
          {run.status === "failed" || run.status === "partial" ? (
            <Button disabled={busy} onClick={onRetry} size="sm" variant="outline">
              <RotateCcw aria-hidden="true" />
              Retry
            </Button>
          ) : null}
        </div>
      </div>

      <div className="mt-6">
        <div className="mb-2 flex items-center justify-between gap-4 text-xs">
          <span className="font-medium text-slate-600">{generationStatusCopy(run.status)}</span>
          <span className="font-semibold tabular-nums text-slate-900">{run.progressPercent}%</span>
        </div>
        <Progress label="Floor-plan generation progress" value={run.progressPercent} />
      </div>

      <ol className="mt-6 grid grid-cols-3 gap-x-2 gap-y-4 sm:grid-cols-6" aria-label="Generation timeline">
        {stages.map((stage, index) => {
          const completed = index < currentIndex || (runComplete && index === currentIndex);
          const current = index === currentIndex && !runComplete;
          return (
            <li className="relative min-w-0 text-center" key={stage.label}>
              <span
                className={cn(
                  "relative mx-auto flex size-7 items-center justify-center rounded-full border text-[11px] font-semibold",
                  completed && "border-emerald-200 bg-emerald-50 text-emerald-700",
                  current && "border-violet-300 bg-violet-50 text-violet-700",
                  !completed && !current && "border-slate-200 bg-slate-50 text-slate-400",
                )}
              >
                {completed ? <Check aria-hidden="true" className="size-3.5" /> : index + 1}
                {current ? (
                  <motion.span
                    animate={reducedMotion ? undefined : { scale: [0.8, 1.35], opacity: [0.55, 0] }}
                    className="absolute inset-0 rounded-full border border-violet-400"
                    transition={{ duration: 1.6, ease: "easeOut", repeat: Infinity }}
                  />
                ) : null}
              </span>
              <span className={cn("mt-2 block truncate text-[11px] text-slate-400", (current || completed) && "text-slate-700")}>
                {stage.label}
              </span>
            </li>
          );
        })}
      </ol>

      <div className="mt-6 grid grid-cols-2 gap-4 border-t border-slate-200 pt-5 text-xs text-slate-500 sm:grid-cols-4">
        <RunMetric icon={Clock3} label="Progress" value={`${run.progressPercent}%`} />
        <RunMetric
          icon={Sparkles}
          label="Solver attempts"
          value={`${run.failureUsage.solverAttempts}/${run.failureBudget.maxSolverAttempts}`}
        />
        <RunMetric
          icon={XCircle}
          label="Invalid candidates"
          value={`${run.failureUsage.invalidCandidates}/${run.failureBudget.maxInvalidCandidates}`}
        />
        <RunMetric
          icon={ShieldCheck}
          label="Cost estimate"
          value={formatMicrousd(run.estimatedCostMicrousd)}
        />
      </div>
      {run.failureCode ? (
        <p className="mt-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-700">
          {formatLabel(run.failureCode)}
        </p>
      ) : null}
      </div>
    </Panel>
  );
}

function OptionInspector({
  busy,
  canRegenerate,
  onAccept,
  onReject,
  onRejectConfirm,
  onRegenerate,
  onRejectionReasonChange,
  onValidate,
  option,
  rejecting,
  rejectionReason,
}: {
  busy: boolean;
  canRegenerate: boolean;
  onAccept: () => void;
  onReject: () => void;
  onRejectConfirm: () => void;
  onRegenerate: () => void;
  onRejectionReasonChange: (value: string) => void;
  onValidate: () => void;
  option: FloorPlanOption;
  rejecting: boolean;
  rejectionReason: string;
}) {
  const satisfied = option.constraintTrace.filter((item) => item.status === "satisfied").length;
  const editable = option.status === "valid";
  const warningCount = option.warnings.length + option.validation.warnings.length;
  return (
    <Panel className="h-fit overflow-hidden border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 px-5 py-4">
        <SectionHeader title="Design review" />
        <p className="mt-1 text-xs leading-5 text-slate-500">
          Inspect quality signals before creating an immutable version.
        </p>
      </div>

      <div className="space-y-5 px-5 py-5">
      <ScoreMeter label="Overall confidence" value={option.confidence} />

      <dl className="grid grid-cols-2 gap-x-5 gap-y-4 border-y border-slate-200 py-4 text-sm">
        <ReviewMetric label="Gross area" value={formatArea(option.areaSummary.grossAreaM2)} />
        <ReviewMetric label="Efficiency" value={formatPercent(option.areaSummary.efficiencyPercent)} />
        <ReviewMetric label="Diversity" value={`${Math.round(option.diversityScore * 100)}%`} />
        <ReviewMetric label="Constraints" value={`${satisfied}/${option.constraintTrace.length}`} />
      </dl>

      {warningCount ? (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-3">
          <div className="flex items-center gap-2 text-xs font-semibold text-amber-800">
            <AlertTriangle aria-hidden="true" className="size-4" />
            {warningCount} validation warning{warningCount === 1 ? "" : "s"}
          </div>
          <ul className="mt-2 space-y-1.5 text-xs leading-5 text-amber-700">
            {[...option.warnings, ...option.validation.warnings].slice(0, 3).map((warning, index) => (
              <li key={`${warningText(warning)}-${index}`}>{warningText(warning)}</li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2.5 text-xs font-medium text-emerald-700">
          <ShieldCheck aria-hidden="true" className="size-4" />
          Deterministic geometry validation passed
        </div>
      )}

      <div>
        <h3 className="text-sm font-semibold text-slate-900">Constraint trace</h3>
        <ul className="mt-3 space-y-3">
          {option.constraintTrace.map((item) => (
            <li className="flex gap-3 text-xs leading-5" key={item.code}>
              {item.status === "satisfied" ? (
                <CheckCircle2 aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-emerald-600" />
              ) : (
                <AlertTriangle
                  aria-hidden="true"
                  className={cn(
                    "mt-0.5 size-4 shrink-0",
                    item.status === "violated" ? "text-rose-600" : "text-amber-600",
                  )}
                />
              )}
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-medium text-slate-800">{formatLabel(item.code)}</p>
                  <span className="text-[10px] font-semibold uppercase text-slate-400">
                    {formatLabel(item.status)}
                  </span>
                </div>
                <p className="mt-0.5 text-slate-500">{item.reason}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>

      <div className="border-t border-slate-200 pt-5">
        <h3 className="text-sm font-semibold text-slate-900">Design explanation</h3>
        <ul className="mt-3 space-y-3">
          {option.majorDecisions.map((decision) => (
            <li className="text-xs leading-5" key={decision.code}>
              <div className="flex items-start justify-between gap-3">
                <p className="font-medium text-slate-800">{decision.title}</p>
                <span className="shrink-0 tabular-nums text-slate-400">
                  {Math.round(decision.confidence * 100)}%
                </span>
              </div>
              <p className="mt-0.5 text-slate-500">{decision.explanation}</p>
            </li>
          ))}
        </ul>
      </div>

      <details className="border-t border-slate-200 pt-4 text-xs">
        <summary className="cursor-pointer font-medium text-slate-700 outline-none focus-visible:ring-2 focus-visible:ring-violet-500">
          Design provenance
        </summary>
        <dl className="mt-3 space-y-2 text-slate-500">
          <SourceRow label="Deterministic seed" value={option.deterministicSeed} />
          <SourceRow label="Geometry engine" value={option.geometryEngineVersion} />
          <SourceRow label="Geometry hash" value={option.geometryHash.slice(0, 12)} />
        </dl>
      </details>

      {rejecting ? (
        <div className="space-y-3 border-t border-slate-200 pt-5">
          <FormField htmlFor="floor-plan-rejection" label="Rejection reason">
            <Textarea
              id="floor-plan-rejection"
              maxLength={1000}
              onChange={(event) => onRejectionReasonChange(event.target.value)}
              value={rejectionReason}
            />
          </FormField>
          <div className="flex gap-2">
            <Button className="flex-1" onClick={onReject} size="sm" variant="ghost">
              Cancel
            </Button>
            <Button
              className="flex-1"
              disabled={busy || rejectionReason.trim().length < 4}
              onClick={onRejectConfirm}
              size="sm"
              variant="destructive"
            >
              Reject
            </Button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-2 border-t border-slate-200 pt-5">
          <Button
            className="col-span-2 compose-floor-action"
            disabled={!canRegenerate || busy}
            onClick={onRegenerate}
            variant="outline"
          >
            <RotateCcw aria-hidden="true" />
            Regenerate options
          </Button>
          <Button
            className="col-span-2"
            disabled={busy}
            onClick={onValidate}
            variant="outline"
          >
            <ListChecks aria-hidden="true" />
            Validate geometry
          </Button>
          <Button disabled={!editable || busy} onClick={onReject} variant="outline">
            <XCircle aria-hidden="true" />
            Reject
          </Button>
          <Button className="compose-floor-action" disabled={!editable || busy} onClick={onAccept}>
            <CheckCircle2 aria-hidden="true" />
            Accept
          </Button>
        </div>
      )}
      <p className="text-xs leading-5 text-amber-700">
        Conceptual Design - Not for Construction. Acceptance does not imply structural or regulatory approval.
      </p>
      </div>
    </Panel>
  );
}

function ComparisonPanel({
  comparison,
  onClose,
}: {
  comparison: FloorPlanComparison;
  onClose: () => void;
}) {
  const reducedMotion = useReducedMotion();
  return (
    <section aria-labelledby="floor-plan-comparison-title" className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-slate-950" id="floor-plan-comparison-title">
            Side-by-side comparison
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Best values are identified per metric, not as an overall design recommendation.
          </p>
        </div>
        <Button aria-label="Close comparison" onClick={onClose} size="icon" variant="ghost">
          <X aria-hidden="true" />
        </Button>
      </div>
      <div className="flex snap-x gap-3 overflow-x-auto pb-2" data-floor-scroll>
        {comparison.options.map((option, index) => {
          const bestCount = comparison.metrics.filter((metric) => metric.bestOptionId === option.id).length;
          return (
            <motion.article
              animate={{ opacity: 1, y: 0 }}
              className="min-w-[250px] flex-1 snap-start overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm sm:min-w-[280px]"
              initial={reducedMotion ? false : { opacity: 0, y: 8 }}
              key={option.id}
              transition={{ delay: reducedMotion ? 0 : index * 0.04, duration: 0.2 }}
            >
              <div className="border-b border-slate-200 px-4 py-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase text-violet-700">
                      Option {option.optionNumber}
                    </p>
                    <h3 className="mt-1 text-sm font-semibold text-slate-900">{option.title}</h3>
                  </div>
                  {bestCount ? (
                    <Badge className="rounded-md" variant="success">{bestCount} best</Badge>
                  ) : null}
                </div>
                <ScoreMeter className="mt-4" label="Confidence" value={option.confidence} />
              </div>
              <dl className="divide-y divide-slate-200 px-4">
                {comparison.metrics.map((metric) => {
                  const best = metric.bestOptionId === option.id;
                  return (
                    <div className="flex items-center justify-between gap-4 py-3 text-xs" key={metric.code}>
                      <dt className="text-slate-500">{metric.label}</dt>
                      <dd className={cn("flex items-center gap-1.5 font-medium text-slate-800", best && "text-emerald-700")}>
                        {best ? <Check aria-hidden="true" className="size-3.5" /> : null}
                        {formatMetric(metric.values[option.id])}
                      </dd>
                    </div>
                  );
                })}
              </dl>
            </motion.article>
          );
        })}
      </div>
    </section>
  );
}

function DesignVersionsPanel({
  busy,
  designs,
  onDelete,
  onRestore,
}: {
  busy: boolean;
  designs: FloorPlanDesignVersion[];
  onDelete: (design: FloorPlanDesignVersion) => void;
  onRestore: (design: FloorPlanDesignVersion) => void;
}) {
  return (
    <Panel className="border-slate-200 bg-white p-5 shadow-sm">
      <SectionHeader
        action={<Badge className="rounded-md" variant="neutral">{designs.length}</Badge>}
        title="Design versions"
      />
      {designs.length ? (
        <ol className="mt-4 divide-y divide-slate-200 border-y border-slate-200">
          {designs.map((design) => (
            <li className="py-3 text-sm" key={design.id}>
              <div className="flex items-center justify-between gap-3">
                <p className="font-medium text-slate-900">{design.name}</p>
                <span className="text-xs text-slate-500">v{design.version}</span>
              </div>
              <p className="mt-1 text-xs text-slate-500">
                {new Date(design.acceptedAt).toLocaleString()} | {design.sourceProvider} |{" "}
                {formatMicrousd(design.generationCostMicrousd)}
              </p>
              {design.restoredFromDesignVersionId ? (
                <p className="mt-1 text-xs text-violet-600">Restored from a previous version</p>
              ) : null}
              <div className="mt-3 grid grid-cols-2 gap-2">
                <Button
                  disabled={busy}
                  onClick={() => onRestore(design)}
                  size="sm"
                  variant="outline"
                >
                  <RotateCcw aria-hidden="true" />
                  Restore
                </Button>
                <Button
                  disabled={busy}
                  onClick={() => onDelete(design)}
                  size="sm"
                  variant="ghost"
                >
                  Hide
                </Button>
              </div>
            </li>
          ))}
        </ol>
      ) : (
        <p className="mt-4 text-sm leading-5 text-slate-500">
          Accepted options will appear here as immutable design versions.
        </p>
      )}
    </Panel>
  );
}

function SourceRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-slate-100 py-2.5 last:border-b-0">
      <dt className="text-slate-500">{label}</dt>
      <dd className="min-w-0 break-words text-right font-medium text-slate-800">
        {value ?? "Unavailable"}
      </dd>
    </div>
  );
}

function ReviewMetric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="mt-1 font-semibold tabular-nums text-slate-900">{value}</dd>
    </div>
  );
}

function ScoreMeter({
  className,
  label,
  value,
}: {
  className?: string;
  label: string;
  value: number;
}) {
  const percentage = Math.max(0, Math.min(100, Math.round(value * 100)));
  return (
    <div className={className}>
      <div className="flex items-center justify-between gap-3 text-xs">
        <span className="font-medium text-slate-600">{label}</span>
        <span className="font-semibold tabular-nums text-slate-900">{percentage}%</span>
      </div>
      <div
        aria-label={`${label}: ${percentage}%`}
        aria-valuemax={100}
        aria-valuemin={0}
        aria-valuenow={percentage}
        className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100"
        role="progressbar"
      >
        <motion.div
          animate={{ width: `${percentage}%` }}
          className="h-full rounded-full bg-violet-600"
          initial={false}
          transition={{ duration: 0.28, ease: "easeOut" }}
        />
      </div>
    </div>
  );
}

function BudgetInput({
  label,
  max,
  min,
  onChange,
  value,
}: {
  label: string;
  max: number;
  min: number;
  onChange: (value: number) => void;
  value: number;
}) {
  const id = React.useId();
  return (
    <label className="space-y-2 text-xs text-muted-foreground" htmlFor={id}>
      {label}
      <Input
        className="mt-2"
        id={id}
        max={max}
        min={min}
        onChange={(event) => onChange(Math.min(max, Math.max(min, Number(event.target.value))))}
        type="number"
        value={value}
      />
    </label>
  );
}

function RunMetric({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof History;
  label: string;
  value: string;
}) {
  return (
    <div className="flex gap-2">
      <Icon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      <div>
        <p>{label}</p>
        <p className="mt-1 font-medium text-foreground tabular-nums">{value}</p>
      </div>
    </div>
  );
}

function OptionGallerySkeleton() {
  return (
    <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3" aria-label="Loading floor-plan options">
      {[0, 1, 2].map((item) => (
        <div className="overflow-hidden rounded-lg border border-slate-200 bg-white" key={item}>
          <Skeleton className="aspect-[4/3] w-full rounded-none" />
          <div className="space-y-3 border-t border-slate-200 p-4">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-3 w-1/2" />
            <Skeleton className="h-9 w-full" />
          </div>
        </div>
      ))}
    </div>
  );
}

function InlineError({
  description,
  onRetry,
  title,
}: {
  description: string;
  onRetry: () => void;
  title: string;
}) {
  return (
    <div className="flex flex-col gap-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 items-start gap-3">
        <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-rose-600" />
        <div>
          <p className="text-sm font-semibold text-rose-800">{title}</p>
          <p className="mt-1 text-xs leading-5 text-rose-700">{description}</p>
        </div>
      </div>
      <Button className="shrink-0 bg-white" onClick={onRetry} size="sm" variant="outline">
        <RotateCcw aria-hidden="true" />
        Retry
      </Button>
    </div>
  );
}

function ReviewEmptyState({ onOpenOptions }: { onOpenOptions: () => void }) {
  return (
    <Panel className="border-slate-200 bg-white shadow-sm">
      <EmptyState
        action={
          <Button className="xl:hidden" onClick={onOpenOptions} variant="outline">
            <LayoutGrid aria-hidden="true" />
            Open options
          </Button>
        }
        description="Choose a validated option to inspect its geometry, area summary, confidence, constraints, and design explanation."
        icon={Ruler}
        title="Select an option to review"
      />
    </Panel>
  );
}

function FloorPlanPageSkeleton() {
  return (
    <div className="compose-floor-plan-light -mx-4 -my-6 min-h-[calc(100dvh-4rem)] space-y-5 bg-[#f7f8fb] px-4 py-5 sm:-mx-6 sm:px-6 lg:-mx-8 lg:-my-8 lg:px-6 lg:py-6">
      <div className="mx-auto w-full max-w-[1540px] space-y-5" aria-label="Loading Floor Plan Generator">
        <div className="flex items-center gap-3 border-b border-slate-200 pb-4">
          <Skeleton className="size-9 shrink-0 rounded-md" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-5 w-64 max-w-full" />
            <Skeleton className="h-3 w-40 max-w-full" />
          </div>
        </div>
        <Skeleton className="h-24 w-full rounded-lg" />
        <div className="grid gap-4 xl:grid-cols-[330px_minmax(0,1fr)]">
          <div className="space-y-4">
            <Skeleton className="h-80 w-full rounded-lg" />
            <Skeleton className="h-[520px] w-full rounded-lg" />
          </div>
          <div className="space-y-4">
            <Skeleton className="h-60 w-full rounded-lg" />
            <div className="rounded-lg border border-slate-200 bg-white p-5">
              <OptionGallerySkeleton />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function formatLabel(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatMetric(value: unknown): string {
  if (typeof value === "number") return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  return String(value ?? "-");
}

function formatArea(value: number | string | null | undefined): string {
  const numericValue = coerceNumber(value);
  return numericValue === null ? "Unavailable" : `${numericValue.toFixed(1)} m2`;
}

function formatPercent(value: number | string | null | undefined): string {
  const numericValue = coerceNumber(value);
  return numericValue === null ? "Unavailable" : `${numericValue.toFixed(1)}%`;
}

function coerceNumber(value: number | string | null | undefined): number | null {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function warningText(warning: Record<string, unknown>): string {
  for (const key of ["message", "reason", "description", "code"]) {
    if (typeof warning[key] === "string" && warning[key]) return String(warning[key]);
  }
  return "Review the validation details for this geometry.";
}

function generationStatusCopy(status: string): string {
  const copy: Record<string, string> = {
    queued: "Preparing generation resources",
    preflighting: "Validating source versions and limits",
    building_context: "Assembling the approved project context",
    generating: "Developing distinct spatial concepts",
    solving: "Resolving room geometry and circulation",
    validating: "Running deterministic geometry checks",
    completed: "All requested options are ready",
    partial: "Valid options are ready; some candidates were exhausted",
    failed: "Generation stopped before a valid result was completed",
    cancelled: "Generation was stopped",
  };
  return copy[status] ?? formatLabel(status);
}

function formatMicrousd(value: number): string {
  if (!value) return "$0.00";
  return `$${(value / 1_000_000).toFixed(4)}`;
}
