"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useAuth } from "@clerk/nextjs";
import type { ProjectDetail } from "@compose-ai/shared";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Building2,
  Check,
  CheckCircle2,
  CircleDashed,
  ClipboardCheck,
  Compass,
  FileText,
  Home,
  Loader2,
  Map,
  Plus,
  Save,
  Sparkles,
  Trash2,
  UserRound,
  type LucideIcon,
} from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useRouter } from "next/navigation";
import * as React from "react";
import {
  useFieldArray,
  useForm,
  type FieldPath,
  type UseFieldArrayReturn,
  type UseFormRegisterReturn,
  type UseFormReturn,
} from "react-hook-form";

import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useProjectDetail } from "@/hooks/use-projects";
import { useSerializedAutosave, type AutosaveStatus } from "@/hooks/use-serialized-autosave";
import { completeProject, createProject, updateProject } from "@/lib/api/projects";
import {
  clearProjectRecovery,
  clearProjectRecoveryRevision,
  readProjectRecovery,
  writeProjectRecovery,
} from "@/lib/projects/recovery";
import {
  emptyProjectValues,
  projectToWizardValues,
  projectTypes,
  projectWizardSchema,
  type ProjectWizardValues,
  wizardValuesToCreate,
  wizardValuesToUpdate,
} from "@/lib/projects/project-form";
import { cn } from "@/lib/utils";

interface ProjectWizardProps {
  projectId?: string;
}

interface RecoveryScope {
  organizationId: string;
  projectId: string | null;
  userId: string;
}

interface WizardSnapshot {
  revision: number;
  scope: RecoveryScope;
  step: number;
  values: ProjectWizardValues;
}

const steps = [
  {
    description: "Identity and standards",
    icon: Building2,
    label: "Project information",
    shortLabel: "Project",
    tip: "Start with the minimum details needed to reserve a clean project record.",
  },
  {
    description: "Contacts and address",
    icon: UserRound,
    label: "Client and site",
    shortLabel: "Site",
    tip: "Client details can stay empty for your own home or early concept work.",
  },
  {
    description: "Site geometry and access",
    icon: Map,
    label: "Plot information",
    shortLabel: "Plot",
    tip: "Approximate dimensions are enough now. Exact boundaries remain reserved for Plot Intelligence.",
  },
  {
    description: "Rooms, budget, and preferences",
    icon: Sparkles,
    label: "Preferences",
    shortLabel: "Prefs",
    tip: "These inputs become the first structured requirement profile for AI Architect.",
  },
  {
    description: "Validate and complete",
    icon: ClipboardCheck,
    label: "Review",
    shortLabel: "Review",
    tip: "Confirm the draft before Compose unlocks downstream design workflows.",
  },
] as const;

const stepToneClasses = [
  "from-violet-500 to-blue-500",
  "from-sky-500 to-violet-500",
  "from-blue-500 to-cyan-500",
  "from-violet-500 to-fuchsia-500",
  "from-emerald-500 to-blue-500",
] as const;

const stepFields: Record<number, FieldPath<ProjectWizardValues>[]> = {
  1: ["name", "projectType", "unitSystem", "currency", "country", "description", "tags"],
  2: [
    "clientName",
    "clientCompany",
    "clientEmail",
    "clientPhone",
    "clientAddress",
    "addressLine1",
    "addressLine2",
    "city",
    "region",
    "postalCode",
    "latitude",
    "longitude",
  ],
  3: [
    "plotLength",
    "plotWidth",
    "plotArea",
    "plotShape",
    "roadDirectionPrimary",
    "roadDirectionSecondary",
    "openSides",
    "cornerPlot",
  ],
  4: [
    "bedrooms",
    "bathrooms",
    "floors",
    "parkingSpaces",
    "budget",
    "constructionQuality",
    "preferredStyle",
    "vastuPreference",
    "notes",
    "roomRequirements",
  ],
  5: [],
};

function formatLabel(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

export function ProjectWizard({ projectId }: ProjectWizardProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { getToken, isLoaded, isSignedIn, orgId, userId } = useAuth();
  const reduceMotion = useReducedMotion();
  const projectQuery = useProjectDetail(projectId ?? null);
  const form = useForm<ProjectWizardValues>({
    defaultValues: emptyProjectValues,
    mode: "onBlur",
    resolver: zodResolver(projectWizardSchema),
  });
  const rooms = useFieldArray({ control: form.control, name: "roomRequirements" });
  const [step, setStep] = React.useState(1);
  const [initialized, setInitialized] = React.useState(false);
  const [recovered, setRecovered] = React.useState(false);
  const [hasUnsaved, setHasUnsaved] = React.useState(false);
  const [actionError, setActionError] = React.useState<string | null>(null);
  const [completing, setCompleting] = React.useState(false);
  const projectIdRef = React.useRef<string | null>(projectId ?? null);
  const versionRef = React.useRef<number>(1);
  const revisionRef = React.useRef(0);
  const latestRevisionRef = React.useRef(0);
  const idempotencyKeyRef = React.useRef<string | null>(null);
  const autosaveTimerRef = React.useRef<number | null>(null);
  const previousStepRef = React.useRef(1);

  const organizationId = orgId ?? "personal";
  const makeScope = React.useCallback(
    (activeProjectId: string | null): RecoveryScope => ({
      organizationId,
      projectId: activeProjectId,
      userId: userId ?? "unknown",
    }),
    [organizationId, userId],
  );

  const saveSnapshot = React.useCallback(
    async (snapshot: WizardSnapshot): Promise<ProjectDetail> => {
      const token = await getToken();
      if (!token) throw new Error("Missing Clerk session token.");
      let activeProjectId = projectIdRef.current;

      if (!activeProjectId) {
        idempotencyKeyRef.current ??= crypto.randomUUID();
        const created = await createProject(
          token,
          wizardValuesToCreate(snapshot.values),
          idempotencyKeyRef.current,
        );
        activeProjectId = created.id;
        projectIdRef.current = created.id;
        versionRef.current = created.version;
        router.replace(`/projects/${created.id}/edit`);
      }

      const updated = await updateProject(
        token,
        activeProjectId,
        versionRef.current,
        wizardValuesToUpdate(snapshot.values, snapshot.step),
      );
      versionRef.current = updated.version;
      return updated;
    },
    [getToken, router],
  );

  const onConfirmed = React.useCallback(
    (snapshot: WizardSnapshot, result: ProjectDetail) => {
      clearProjectRecoveryRevision(snapshot.scope, snapshot.revision);
      projectIdRef.current = result.id;
      versionRef.current = result.version;
      queryClient.setQueryData(["projects", "detail", result.id], result);
      void queryClient.invalidateQueries({ queryKey: ["projects", "list"] });
      void queryClient.invalidateQueries({ queryKey: ["projects", "summary"] });
      if (latestRevisionRef.current === snapshot.revision) setHasUnsaved(false);
    },
    [queryClient],
  );

  const {
    flush: flushAutosave,
    queue: queueAutosave,
    retry: retryAutosave,
    status: autosaveStatus,
  } = useSerializedAutosave({ onConfirmed, save: saveSnapshot });

  const createSnapshot = React.useCallback((): WizardSnapshot => {
    const revision = revisionRef.current + 1;
    revisionRef.current = revision;
    latestRevisionRef.current = revision;
    return {
      revision,
      scope: makeScope(projectIdRef.current),
      step,
      values: form.getValues(),
    };
  }, [form, makeScope, step]);

  React.useEffect(() => {
    if (!isLoaded || !isSignedIn || !userId || initialized) return;
    if (projectId && projectQuery.isLoading) return;
    if (projectId && !projectQuery.data) return;

    const scope = makeScope(projectId ?? null);
    const recovery = readProjectRecovery(scope);
    const serverValues = projectQuery.data
      ? projectToWizardValues(projectQuery.data)
      : emptyProjectValues;
    let initialValues = serverValues;
    let initialStep = projectQuery.data?.wizardStep ?? 1;
    if (recovery) {
      const recoveredValues = projectWizardSchema.safeParse(recovery.snapshot.values);
      if (recoveredValues.success) {
        initialValues = recoveredValues.data;
        initialStep =
          typeof recovery.snapshot.step === "number" ? recovery.snapshot.step : initialStep;
        revisionRef.current = recovery.revision;
        latestRevisionRef.current = recovery.revision;
        setRecovered(true);
        setHasUnsaved(true);
      }
    }
    if (projectQuery.data) {
      projectIdRef.current = projectQuery.data.id;
      versionRef.current = projectQuery.data.version;
    }
    form.reset(initialValues);
    const boundedInitialStep = Math.min(Math.max(initialStep, 1), 5);
    previousStepRef.current = boundedInitialStep;
    setStep(boundedInitialStep);
    setInitialized(true);
  }, [
    form,
    initialized,
    isLoaded,
    isSignedIn,
    makeScope,
    projectId,
    projectQuery.data,
    projectQuery.isLoading,
    userId,
  ]);

  React.useEffect(() => {
    if (!initialized) return;
    const subscription = form.watch(() => {
      const snapshot = createSnapshot();
      setHasUnsaved(true);
      writeProjectRecovery(snapshot.scope, snapshot.revision, {
        step: snapshot.step,
        values: snapshot.values,
      });
      if (autosaveTimerRef.current) window.clearTimeout(autosaveTimerRef.current);
      autosaveTimerRef.current = window.setTimeout(() => {
        if (
          snapshot.values.name.trim().length >= 2 &&
          projectWizardSchema.safeParse(snapshot.values).success
        ) {
          queueAutosave(snapshot);
        }
      }, 850);
    });
    return () => {
      subscription.unsubscribe();
      if (autosaveTimerRef.current) window.clearTimeout(autosaveTimerRef.current);
    };
  }, [createSnapshot, form, initialized, queueAutosave]);

  React.useEffect(() => {
    if (!initialized || previousStepRef.current === step) return;
    previousStepRef.current = step;
    const snapshot = createSnapshot();
    setHasUnsaved(true);
    writeProjectRecovery(snapshot.scope, snapshot.revision, {
      step: snapshot.step,
      values: snapshot.values,
    });
    if (autosaveTimerRef.current) window.clearTimeout(autosaveTimerRef.current);
    autosaveTimerRef.current = window.setTimeout(() => {
      if (
        snapshot.values.name.trim().length >= 2 &&
        projectWizardSchema.safeParse(snapshot.values).success
      ) {
        queueAutosave(snapshot);
      }
    }, 850);
  }, [createSnapshot, initialized, queueAutosave, step]);

  React.useEffect(() => {
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!hasUnsaved) return;
      event.preventDefault();
      event.returnValue = "";
    };
    const onDocumentClick = (event: MouseEvent) => {
      if (
        !hasUnsaved ||
        event.defaultPrevented ||
        event.button !== 0 ||
        event.altKey ||
        event.ctrlKey ||
        event.metaKey ||
        event.shiftKey
      ) {
        return;
      }
      const link = event.target instanceof Element ? event.target.closest("a[href]") : null;
      if (!(link instanceof HTMLAnchorElement) || link.target === "_blank" || link.download) return;
      const destination = new URL(link.href, window.location.href);
      const currentLocation = `${window.location.pathname}${window.location.search}${window.location.hash}`;
      const nextLocation = `${destination.pathname}${destination.search}${destination.hash}`;
      if (destination.origin !== window.location.origin || currentLocation === nextLocation) return;
      if (!window.confirm("Leave this project? Unsaved changes remain recoverable locally.")) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        const snapshot = createSnapshot();
        writeProjectRecovery(snapshot.scope, snapshot.revision, {
          step: snapshot.step,
          values: snapshot.values,
        });
        void flushAutosave(snapshot).catch((error) => {
          setActionError(error instanceof Error ? error.message : "Project save failed.");
        });
      }
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    document.addEventListener("click", onDocumentClick, true);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload);
      document.removeEventListener("click", onDocumentClick, true);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [createSnapshot, flushAutosave, hasUnsaved]);

  const goNext = React.useCallback(async () => {
    const valid = await form.trigger(stepFields[step], { shouldFocus: true });
    if (valid) setStep((current) => Math.min(current + 1, 5));
  }, [form, step]);

  const saveNow = React.useCallback(async () => {
    const valid = await form.trigger(undefined, { shouldFocus: true });
    if (!valid) return;
    const snapshot = createSnapshot();
    writeProjectRecovery(snapshot.scope, snapshot.revision, {
      step: snapshot.step,
      values: snapshot.values,
    });
    setActionError(null);
    try {
      await flushAutosave(snapshot);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Project save failed.");
    }
  }, [createSnapshot, flushAutosave, form]);

  const finishProject = React.useCallback(async () => {
    const values = form.getValues();
    let valid = await form.trigger(undefined, { shouldFocus: true });
    if (!values.projectType) {
      form.setError("projectType", { message: "Project type is required to complete the draft." });
      valid = false;
    }
    if (!values.country) {
      form.setError("country", { message: "Country is required to complete the draft." });
      valid = false;
    }
    if (!valid) return;

    setCompleting(true);
    setActionError(null);
    try {
      const snapshot = createSnapshot();
      writeProjectRecovery(snapshot.scope, snapshot.revision, {
        step: 5,
        values: snapshot.values,
      });
      await flushAutosave({ ...snapshot, step: 5 });
      const token = await getToken();
      const activeProjectId = projectIdRef.current;
      if (!token || !activeProjectId) throw new Error("Project draft is not ready.");
      const completed = await completeProject(token, activeProjectId, versionRef.current);
      versionRef.current = completed.version;
      clearProjectRecovery(makeScope(activeProjectId));
      clearProjectRecovery(makeScope(null));
      setHasUnsaved(false);
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      router.push(`/projects/${activeProjectId}`);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Project completion failed.");
    } finally {
      setCompleting(false);
    }
  }, [createSnapshot, flushAutosave, form, getToken, makeScope, queryClient, router]);

  const cancel = React.useCallback(() => {
    if (
      hasUnsaved &&
      !window.confirm("Leave this project? Unsaved changes remain recoverable locally.")
    ) {
      return;
    }
    router.push("/projects?view=drafts");
  }, [hasUnsaved, router]);

  const currentStep = steps[step - 1];
  const currentIcon = currentStep.icon;
  const progressPercent = ((step - 1) / (steps.length - 1)) * 100;
  const watchedValues = form.watch();
  const readiness = getWizardReadiness(watchedValues);

  if (projectId && projectQuery.isLoading) {
    return <WizardSkeleton />;
  }

  if (projectId && projectQuery.isError) {
    return (
      <div className="compose-project-wizard-light rounded-[1.75rem] border border-rose-100 bg-white p-6 shadow-[0_18px_55px_rgba(51,65,85,0.08)]">
        <h1 className="text-lg font-semibold text-slate-950">Project unavailable</h1>
        <p className="mt-2 text-sm text-slate-600">
          The project could not be loaded for editing.
        </p>
        <Button className="mt-5" onClick={() => projectQuery.refetch()} variant="outline">
          Retry
        </Button>
      </div>
    );
  }

  return (
    <form
      className="compose-project-wizard-light -mx-4 -my-6 min-h-[calc(100dvh-4rem)] px-4 py-6 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8"
      onSubmit={(event) => event.preventDefault()}
    >
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <section className="relative overflow-hidden rounded-[2rem] border border-white/80 bg-white/82 p-5 shadow-[0_24px_80px_rgba(51,65,85,0.10)] backdrop-blur-xl sm:p-7">
          <div aria-hidden="true" className="compose-project-wizard-grid" />
          <div className="relative z-10 flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-2 rounded-full border border-violet-200/80 bg-white/75 px-3 py-1 text-xs font-medium text-violet-700 shadow-sm">
                <Sparkles className="size-3.5" aria-hidden="true" />
                Project creation workspace
              </div>
              <h1 className="mt-4 text-balance text-3xl font-semibold tracking-normal text-slate-950 sm:text-4xl">
                {projectIdRef.current ? "Refine the project brief" : "Create a project without friction"}
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600 sm:text-base">
                Compose saves your draft as you work, keeps local recovery available, and turns the
                essentials into a structured architecture-ready brief.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 lg:w-[22rem] lg:grid-cols-1">
              <AutosaveStatusCard
                hasUnsaved={hasUnsaved}
                onRetry={retryAutosave}
                status={autosaveStatus}
              />
              <ReadinessCard readiness={readiness} />
            </div>
          </div>
        </section>

        <StatusMessages
          actionError={actionError}
          autosaveStatus={autosaveStatus}
          onRetry={retryAutosave}
          recovered={recovered}
        />

        <div className="grid gap-6 lg:grid-cols-[19rem_minmax(0,1fr)]">
          <aside aria-label="Project setup steps" className="lg:sticky lg:top-24 lg:self-start">
            <div className="rounded-[1.5rem] border border-white/80 bg-white/88 p-3 shadow-[0_18px_55px_rgba(51,65,85,0.08)] backdrop-blur-xl">
              <div className="px-2 pb-3 pt-1">
                <div className="flex items-center justify-between text-xs font-medium text-slate-500">
                  <span>Progress</span>
                  <span>{Math.round(progressPercent)}%</span>
                </div>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
                  <motion.div
                    animate={{ width: `${progressPercent}%` }}
                    className="h-full rounded-full bg-gradient-to-r from-violet-500 via-blue-500 to-cyan-400"
                    initial={false}
                    transition={{ duration: reduceMotion ? 0 : 0.28, ease: "easeOut" }}
                  />
                </div>
              </div>
              <ol className="grid grid-cols-5 gap-2 lg:grid-cols-1">
                {steps.map((item, index) => {
                  const stepNumber = index + 1;
                  const active = step === stepNumber;
                  const complete = step > stepNumber;
                  const StepIcon = item.icon;
                  return (
                    <li key={item.label}>
                      <button
                        aria-current={active ? "step" : undefined}
                        className={cn(
                          "group flex w-full min-w-0 items-center justify-center gap-3 rounded-2xl border border-transparent px-2 py-3 text-left text-sm text-slate-500 transition duration-200 hover:border-violet-100 hover:bg-white hover:text-slate-950 hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-300 focus-visible:ring-offset-2 focus-visible:ring-offset-white lg:justify-start lg:px-3",
                          active && "border-violet-200 bg-white text-slate-950 shadow-sm",
                          complete && !active && "text-slate-700",
                        )}
                        onClick={() => setStep(stepNumber)}
                        type="button"
                      >
                        <span
                          className={cn(
                            "relative flex size-9 shrink-0 items-center justify-center rounded-2xl border border-slate-200 bg-slate-50 text-slate-500 transition duration-200 group-hover:border-violet-200 group-hover:bg-violet-50",
                            active &&
                              "border-transparent bg-gradient-to-br text-white shadow-[0_10px_25px_rgba(124,58,237,0.24)]",
                            active && stepToneClasses[index],
                            complete && !active && "border-emerald-200 bg-emerald-50 text-emerald-700",
                          )}
                        >
                          {complete ? (
                            <Check className="size-4" aria-hidden="true" />
                          ) : (
                            <StepIcon className="size-4" aria-hidden="true" />
                          )}
                        </span>
                        <span className="hidden min-w-0 lg:block">
                          <span className="block truncate font-medium">{item.label}</span>
                          <span className="mt-0.5 block truncate text-xs text-slate-500">
                            {item.description}
                          </span>
                        </span>
                        <span className="sr-only">{item.shortLabel}</span>
                      </button>
                    </li>
                  );
                })}
              </ol>
            </div>
          </aside>

          <div className="min-w-0">
            <div className="mb-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_18rem]">
              <StepIntroCard
                description={currentStep.description}
                icon={currentIcon}
                step={step}
                title={currentStep.label}
              />
              <ContextTip tip={currentStep.tip} />
            </div>

            <section className="relative min-w-0 overflow-hidden rounded-[1.75rem] border border-white/80 bg-white/92 p-5 shadow-[0_24px_80px_rgba(51,65,85,0.10)] backdrop-blur-xl sm:p-7">
              <AnimatePresence mode="wait">
                <motion.div
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: reduceMotion ? 0 : -10 }}
                  initial={{ opacity: 0, x: reduceMotion ? 0 : 10 }}
                  key={step}
                  transition={{ duration: reduceMotion ? 0 : 0.2, ease: "easeOut" }}
                >
                  {step === 1 ? <ProjectDetailsStep form={form} /> : null}
                  {step === 2 ? <ClientLocationStep form={form} /> : null}
                  {step === 3 ? <PlotProfileStep form={form} /> : null}
                  {step === 4 ? <RequirementsStep form={form} rooms={rooms} /> : null}
                  {step === 5 ? <ReviewStep values={form.getValues()} /> : null}
                </motion.div>
              </AnimatePresence>
            </section>

            <div className="sticky bottom-4 z-20 mt-5 rounded-[1.35rem] border border-white/80 bg-white/88 p-3 shadow-[0_18px_55px_rgba(51,65,85,0.13)] backdrop-blur-xl">
              <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
                <Button
                  className="text-slate-600 hover:text-slate-950"
                  onClick={cancel}
                  type="button"
                  variant="ghost"
                >
                  Cancel
                </Button>
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
                  <Button onClick={() => void saveNow()} type="button" variant="outline">
                    <Save aria-hidden="true" />
                    Save draft
                  </Button>
                  {step > 1 ? (
                    <Button
                      onClick={() => setStep((current) => current - 1)}
                      type="button"
                      variant="outline"
                    >
                      <ArrowLeft aria-hidden="true" />
                      Back
                    </Button>
                  ) : null}
                  {step < 5 ? (
                    <Button
                      className="compose-project-action min-h-11 bg-gradient-to-r from-violet-600 to-blue-600 text-white shadow-[0_14px_30px_rgba(79,70,229,0.24)] hover:from-violet-500 hover:to-blue-500"
                      onClick={() => void goNext()}
                      type="button"
                    >
                      Continue
                      <ArrowRight aria-hidden="true" />
                    </Button>
                  ) : (
                    <Button
                      className="compose-project-action min-h-11 bg-gradient-to-r from-violet-600 to-blue-600 text-white shadow-[0_14px_30px_rgba(79,70,229,0.24)] hover:from-violet-500 hover:to-blue-500"
                      disabled={completing}
                      onClick={() => void finishProject()}
                      type="button"
                    >
                      {completing ? (
                        <Loader2 className="animate-spin" aria-hidden="true" />
                      ) : (
                        <Check aria-hidden="true" />
                      )}
                      {completing ? "Completing..." : "Complete project"}
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </form>
  );
}

function AutosaveStatusCard({
  hasUnsaved,
  onRetry,
  status,
}: {
  hasUnsaved: boolean;
  onRetry: () => void;
  status: AutosaveStatus;
}) {
  const copy =
    status === "saving"
      ? "Saving draft"
      : status === "saved"
        ? "Saved to Compose"
        : status === "error"
          ? "Save needs retry"
          : hasUnsaved
            ? "Stored locally"
            : "Ready";
  const Icon =
    status === "saving"
      ? Loader2
      : status === "error"
        ? AlertCircle
        : hasUnsaved
          ? CircleDashed
          : CheckCircle2;

  return (
    <div className="rounded-2xl border border-slate-200/75 bg-white/82 p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <span
          className={cn(
            "flex size-10 shrink-0 items-center justify-center rounded-2xl",
            status === "error"
              ? "bg-rose-50 text-rose-600"
              : status === "saving"
                ? "bg-blue-50 text-blue-600"
                : "bg-violet-50 text-violet-700",
          )}
        >
          <Icon
            className={cn("size-4", status === "saving" && "animate-spin")}
            aria-hidden="true"
          />
        </span>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-slate-950">{copy}</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            {status === "error"
              ? "Your browser copy is preserved. Retry when the connection is stable."
              : "Draft recovery remains available if the tab closes unexpectedly."}
          </p>
          {status === "error" ? (
            <button
              className="mt-2 text-xs font-semibold text-violet-700 underline-offset-4 hover:underline"
              onClick={onRetry}
              type="button"
            >
              Retry save
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function ReadinessCard({ readiness }: { readiness: number }) {
  return (
    <div className="rounded-2xl border border-slate-200/75 bg-white/82 p-4 shadow-sm">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-slate-950">Brief readiness</p>
          <p className="mt-1 text-xs text-slate-500">Based on completed project essentials.</p>
        </div>
        <span className="text-xl font-semibold tabular-nums text-slate-950">{readiness}%</span>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
        <motion.div
          animate={{ width: `${readiness}%` }}
          className="h-full rounded-full bg-gradient-to-r from-violet-500 to-blue-500"
          initial={false}
          transition={{ duration: 0.25, ease: "easeOut" }}
        />
      </div>
    </div>
  );
}

function StatusMessages({
  actionError,
  autosaveStatus,
  onRetry,
  recovered,
}: {
  actionError: string | null;
  autosaveStatus: AutosaveStatus;
  onRetry: () => void;
  recovered: boolean;
}) {
  if (!recovered && !actionError) return null;
  return (
    <div className="grid gap-3">
      {recovered ? (
        <div
          className="rounded-2xl border border-violet-200/80 bg-violet-50/80 px-4 py-3 text-sm text-violet-800"
          role="status"
        >
          Recovered unsaved changes from this browser.
        </div>
      ) : null}
      {actionError ? (
        <div
          className="flex flex-col gap-3 rounded-2xl border border-rose-200/80 bg-rose-50/85 px-4 py-3 text-sm text-rose-700 sm:flex-row sm:items-center sm:justify-between"
          role="alert"
        >
          <span>{actionError}</span>
          {autosaveStatus === "error" ? (
            <Button onClick={onRetry} size="sm" type="button" variant="outline">
              Retry save
            </Button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function StepIntroCard({
  description,
  icon: Icon,
  step,
  title,
}: {
  description: string;
  icon: LucideIcon;
  step: number;
  title: string;
}) {
  return (
    <div className="overflow-hidden rounded-[1.5rem] border border-white/80 bg-white/88 p-5 shadow-[0_18px_55px_rgba(51,65,85,0.08)] backdrop-blur-xl">
      <div className="flex items-center gap-4">
        <div
          className={cn(
            "flex size-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br text-white shadow-[0_14px_30px_rgba(79,70,229,0.22)]",
            stepToneClasses[step - 1],
          )}
        >
          <Icon className="size-5" aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase text-violet-700">Step {step} of 5</p>
          <h2 className="mt-1 text-xl font-semibold text-slate-950">{title}</h2>
          <p className="mt-1 text-sm leading-6 text-slate-600">{description}</p>
        </div>
      </div>
    </div>
  );
}

function ContextTip({ tip }: { tip: string }) {
  return (
    <div className="relative overflow-hidden rounded-[1.5rem] border border-blue-100 bg-gradient-to-br from-white to-blue-50/70 p-5 shadow-[0_18px_55px_rgba(51,65,85,0.08)]">
      <div aria-hidden="true" className="compose-project-illustration">
        <span />
        <span />
        <span />
      </div>
      <div className="relative z-10">
        <div className="flex size-9 items-center justify-center rounded-2xl bg-blue-50 text-blue-700">
          <Compass className="size-4" aria-hidden="true" />
        </div>
        <p className="mt-3 text-sm font-medium leading-6 text-slate-700">{tip}</p>
      </div>
    </div>
  );
}

function getWizardReadiness(values: ProjectWizardValues): number {
  const checks = [
    values.name.trim().length >= 2,
    Boolean(values.projectType),
    Boolean(values.country),
    Boolean(values.city || values.addressLine1),
    Boolean(values.plotShape || values.plotArea || values.plotLength || values.plotWidth),
    Number(values.bedrooms || 0) > 0 || Number(values.floors || 0) > 0,
    Boolean(values.preferredStyle || values.constructionQuality || values.notes),
  ];
  const completed = checks.filter(Boolean).length;
  return Math.round((completed / checks.length) * 100);
}

type WizardForm = UseFormReturn<ProjectWizardValues>;

function ProjectDetailsStep({ form }: { form: WizardForm }) {
  const errors = form.formState.errors;
  return (
    <StepSection
      icon={FileText}
      title="Project details"
      description="Set the project identity and regional standards."
    >
      <WizardFieldCard>
        <FormField error={errors.name?.message} htmlFor="name" label="Project name" required>
          <Input id="name" placeholder="Modern family residence" {...form.register("name")} />
        </FormField>
        <div className="grid gap-5 sm:grid-cols-2">
          <FormField error={errors.projectType?.message} htmlFor="projectType" label="Project type">
            <Select id="projectType" {...form.register("projectType")}>
              <option value="">Select project type</option>
              {projectTypes.map((type) => (
                <option key={type} value={type}>
                  {formatLabel(type)}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField htmlFor="unitSystem" label="Unit system">
            <Select id="unitSystem" {...form.register("unitSystem")}>
              <option value="metric">Metric</option>
              <option value="imperial">Imperial</option>
            </Select>
          </FormField>
          <FormField error={errors.currency?.message} htmlFor="currency" label="Currency">
            <Input id="currency" maxLength={3} placeholder="USD" {...form.register("currency")} />
          </FormField>
          <FormField error={errors.country?.message} htmlFor="country" label="Country">
            <Input id="country" maxLength={2} placeholder="US" {...form.register("country")} />
          </FormField>
        </div>
      </WizardFieldCard>
      <WizardFieldCard>
        <FormField description="Separate tags with commas." htmlFor="tags" label="Tags">
          <Input id="tags" placeholder="Residential, Concept" {...form.register("tags")} />
        </FormField>
        <FormField error={errors.description?.message} htmlFor="description" label="Description">
          <Textarea
            id="description"
            placeholder="Describe the project goals, client expectations, or early design intent."
            {...form.register("description")}
          />
        </FormField>
      </WizardFieldCard>
    </StepSection>
  );
}

function ClientLocationStep({ form }: { form: WizardForm }) {
  const errors = form.formState.errors;
  return (
    <StepSection
      icon={Home}
      title="Client and location"
      description="Client information is optional for self-owned projects."
    >
      <WizardFieldCard title="Client profile">
        <div className="grid gap-5 sm:grid-cols-2">
          <FormField htmlFor="clientName" label="Client name">
            <Input id="clientName" {...form.register("clientName")} />
          </FormField>
          <FormField htmlFor="clientCompany" label="Company">
            <Input id="clientCompany" {...form.register("clientCompany")} />
          </FormField>
          <FormField error={errors.clientEmail?.message} htmlFor="clientEmail" label="Email">
            <Input id="clientEmail" type="email" {...form.register("clientEmail")} />
          </FormField>
          <FormField error={errors.clientPhone?.message} htmlFor="clientPhone" label="Phone">
            <Input id="clientPhone" type="tel" {...form.register("clientPhone")} />
          </FormField>
        </div>
        <FormField htmlFor="clientAddress" label="Client address">
          <Textarea id="clientAddress" {...form.register("clientAddress")} />
        </FormField>
      </WizardFieldCard>
      <WizardFieldCard title="Site address">
        <div className="grid gap-5 sm:grid-cols-2">
          <FormField className="sm:col-span-2" htmlFor="addressLine1" label="Address line 1">
            <Input id="addressLine1" {...form.register("addressLine1")} />
          </FormField>
          <FormField className="sm:col-span-2" htmlFor="addressLine2" label="Address line 2">
            <Input id="addressLine2" {...form.register("addressLine2")} />
          </FormField>
          <FormField htmlFor="city" label="City">
            <Input id="city" {...form.register("city")} />
          </FormField>
          <FormField htmlFor="region" label="State or region">
            <Input id="region" {...form.register("region")} />
          </FormField>
          <FormField htmlFor="postalCode" label="Postal code">
            <Input id="postalCode" {...form.register("postalCode")} />
          </FormField>
        </div>
      </WizardFieldCard>
      <WizardFieldCard title="Coordinates">
        <div className="grid gap-5 sm:grid-cols-2">
          <FormField error={errors.latitude?.message} htmlFor="latitude" label="Latitude">
            <Input id="latitude" inputMode="decimal" {...form.register("latitude")} />
          </FormField>
          <FormField error={errors.longitude?.message} htmlFor="longitude" label="Longitude">
            <Input id="longitude" inputMode="decimal" {...form.register("longitude")} />
          </FormField>
        </div>
      </WizardFieldCard>
    </StepSection>
  );
}

function PlotProfileStep({ form }: { form: WizardForm }) {
  const errors = form.formState.errors;
  return (
    <StepSection
      icon={Map}
      title="Plot profile"
      description="Capture site geometry without starting a drawing or editor."
    >
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_18rem]">
        <WizardFieldCard>
          <div className="grid gap-5 sm:grid-cols-2">
            <FormField htmlFor="plotShape" label="Plot shape">
              <Select id="plotShape" {...form.register("plotShape")}>
                <option value="">Select shape</option>
                {["rectangle", "square", "l_shaped", "trapezoid", "irregular", "other"].map(
                  (shape) => (
                    <option key={shape} value={shape}>
                      {formatLabel(shape)}
                    </option>
                  ),
                )}
              </Select>
            </FormField>
            <FormField error={errors.plotArea?.message} htmlFor="plotArea" label="Plot area">
              <Input id="plotArea" inputMode="decimal" {...form.register("plotArea")} />
            </FormField>
            <FormField error={errors.plotLength?.message} htmlFor="plotLength" label="Plot length">
              <Input id="plotLength" inputMode="decimal" {...form.register("plotLength")} />
            </FormField>
            <FormField error={errors.plotWidth?.message} htmlFor="plotWidth" label="Plot width">
              <Input id="plotWidth" inputMode="decimal" {...form.register("plotWidth")} />
            </FormField>
            <FormField error={errors.openSides?.message} htmlFor="openSides" label="Open sides">
              <Input id="openSides" inputMode="numeric" {...form.register("openSides")} />
            </FormField>
            <FormField htmlFor="roadDirectionPrimary" label="Primary road direction">
              <DirectionSelect
                id="roadDirectionPrimary"
                registration={form.register("roadDirectionPrimary")}
              />
            </FormField>
            <FormField
              error={errors.roadDirectionSecondary?.message}
              htmlFor="roadDirectionSecondary"
              label="Secondary road direction"
            >
              <DirectionSelect
                id="roadDirectionSecondary"
                registration={form.register("roadDirectionSecondary")}
              />
            </FormField>
          </div>
          <label className="flex min-h-12 items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 text-sm font-medium text-slate-700 shadow-sm transition hover:border-violet-200 hover:bg-violet-50/40">
            <input
              className="size-4 accent-violet-600"
              type="checkbox"
              {...form.register("cornerPlot")}
            />
            Corner plot
          </label>
        </WizardFieldCard>
        <PlotIllustration />
      </div>
    </StepSection>
  );
}

function RequirementsStep({
  form,
  rooms,
}: {
  form: WizardForm;
  rooms: UseFieldArrayReturn<ProjectWizardValues, "roomRequirements">;
}) {
  const errors = form.formState.errors;
  return (
    <StepSection
      icon={Sparkles}
      title="Requirements"
      description="Describe capacity, quality, budget, and custom spaces."
    >
      <WizardFieldCard title="Core requirements">
        <div className="grid gap-5 sm:grid-cols-2">
          <FormField error={errors.bedrooms?.message} htmlFor="bedrooms" label="Bedrooms">
            <Input id="bedrooms" inputMode="numeric" {...form.register("bedrooms")} />
          </FormField>
          <FormField error={errors.bathrooms?.message} htmlFor="bathrooms" label="Bathrooms">
            <Input id="bathrooms" inputMode="decimal" {...form.register("bathrooms")} />
          </FormField>
          <FormField error={errors.floors?.message} htmlFor="floors" label="Floors">
            <Input id="floors" inputMode="numeric" {...form.register("floors")} />
          </FormField>
          <FormField
            error={errors.parkingSpaces?.message}
            htmlFor="parkingSpaces"
            label="Parking spaces"
          >
            <Input id="parkingSpaces" inputMode="numeric" {...form.register("parkingSpaces")} />
          </FormField>
          <FormField error={errors.budget?.message} htmlFor="budget" label="Budget">
            <Input id="budget" inputMode="decimal" {...form.register("budget")} />
          </FormField>
          <FormField htmlFor="constructionQuality" label="Construction quality">
            <Select id="constructionQuality" {...form.register("constructionQuality")}>
              <option value="">Not specified</option>
              {["economy", "standard", "premium", "luxury"].map((quality) => (
                <option key={quality} value={quality}>
                  {formatLabel(quality)}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField htmlFor="preferredStyle" label="Preferred style">
            <Input
              id="preferredStyle"
              placeholder="Contemporary, minimal, tropical..."
              {...form.register("preferredStyle")}
            />
          </FormField>
          <FormField htmlFor="vastuPreference" label="Vastu preference">
            <Select id="vastuPreference" {...form.register("vastuPreference")}>
              <option value="not_required">Not required</option>
              <option value="preferred">Preferred</option>
              <option value="strict">Strict</option>
            </Select>
          </FormField>
        </div>
        <FormField htmlFor="notes" label="Requirements notes">
          <Textarea
            id="notes"
            placeholder="Capture lifestyle needs, family routines, privacy expectations, or must-have spaces."
            {...form.register("notes")}
          />
        </FormField>
      </WizardFieldCard>
      <WizardFieldCard title="Custom rooms">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="text-sm font-semibold text-slate-950">Additional spaces</h3>
            <p className="mt-1 text-xs text-slate-500">
              Add spaces beyond the standard room counts.
            </p>
          </div>
          <Button
            onClick={() =>
              rooms.append({
                minimumArea: "",
                name: "",
                notes: "",
                preferredFloor: "",
                quantity: "1",
                roomType: "",
              })
            }
            size="sm"
            type="button"
            variant="outline"
          >
            <Plus aria-hidden="true" />
            Add room
          </Button>
        </div>
        <div className="mt-4 space-y-3">
          {rooms.fields.map((field, index) => (
            <motion.div
              animate={{ opacity: 1, y: 0 }}
              className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:grid-cols-2"
              initial={{ opacity: 0, y: 6 }}
              key={field.id}
              transition={{ duration: 0.18, ease: "easeOut" }}
            >
              <FormField
                error={errors.roomRequirements?.[index]?.name?.message}
                htmlFor={`room-${index}-name`}
                label="Room name"
              >
                <Input
                  id={`room-${index}-name`}
                  {...form.register(`roomRequirements.${index}.name`)}
                />
              </FormField>
              <FormField htmlFor={`room-${index}-type`} label="Room type">
                <Input
                  id={`room-${index}-type`}
                  {...form.register(`roomRequirements.${index}.roomType`)}
                />
              </FormField>
              <FormField htmlFor={`room-${index}-quantity`} label="Quantity">
                <Input
                  id={`room-${index}-quantity`}
                  inputMode="numeric"
                  {...form.register(`roomRequirements.${index}.quantity`)}
                />
              </FormField>
              <FormField htmlFor={`room-${index}-area`} label="Minimum area">
                <Input
                  id={`room-${index}-area`}
                  inputMode="decimal"
                  {...form.register(`roomRequirements.${index}.minimumArea`)}
                />
              </FormField>
              <FormField htmlFor={`room-${index}-floor`} label="Preferred floor">
                <Input
                  id={`room-${index}-floor`}
                  inputMode="numeric"
                  {...form.register(`roomRequirements.${index}.preferredFloor`)}
                />
              </FormField>
              <FormField
                className="sm:col-span-2"
                htmlFor={`room-${index}-notes`}
                label="Room notes"
              >
                <Textarea
                  id={`room-${index}-notes`}
                  {...form.register(`roomRequirements.${index}.notes`)}
                />
              </FormField>
              <div className="sm:col-span-2 flex justify-end">
                <Button onClick={() => rooms.remove(index)} size="sm" type="button" variant="ghost">
                  <Trash2 aria-hidden="true" />
                  Remove room
                </Button>
              </div>
            </motion.div>
          ))}
          {rooms.fields.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-4 py-8 text-center">
              <p className="text-sm font-medium text-slate-700">No custom room requirements</p>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                Add studios, servant rooms, terraces, pooja rooms, or special-purpose spaces here.
              </p>
            </div>
          ) : null}
        </div>
      </WizardFieldCard>
    </StepSection>
  );
}

function ReviewStep({ values }: { values: ProjectWizardValues }) {
  const rows = [
    { label: "Project", value: values.name || "Not set" },
    {
      label: "Type",
      required: !values.projectType,
      value: values.projectType ? formatLabel(values.projectType) : "Required before completion",
    },
    { label: "Country", required: !values.country, value: values.country || "Required before completion" },
    { label: "Client", value: values.clientName || values.clientCompany || "Self-owned / not specified" },
    { label: "Site", value: values.city || values.addressLine1 || "Not specified" },
    { label: "Plot", value: values.plotShape ? formatLabel(values.plotShape) : "Not specified" },
    {
      label: "Requirements",
      value: `${values.bedrooms || 0} bedrooms, ${values.bathrooms || 0} bathrooms, ${
        values.floors || 1
      } floors`,
    },
    { label: "Custom rooms", value: String(values.roomRequirements.length) },
  ];
  const metrics = [
    { label: "Bedrooms", value: values.bedrooms || "0" },
    { label: "Bathrooms", value: values.bathrooms || "0" },
    { label: "Floors", value: values.floors || "1" },
    {
      label: "Budget",
      value: values.budget ? `${values.currency || ""} ${values.budget}`.trim() : "Not set",
    },
  ];
  return (
    <StepSection
      icon={ClipboardCheck}
      title="Review project"
      description="Confirm the structured brief before activating the project."
    >
      <div className="grid gap-4 sm:grid-cols-4">
        {metrics.map((metric) => (
          <div
            className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
            key={metric.label}
          >
            <p className="text-xs font-medium text-slate-500">{metric.label}</p>
            <p className="mt-2 truncate text-lg font-semibold text-slate-950">{metric.value}</p>
          </div>
        ))}
      </div>
      <WizardFieldCard title="Activation checklist">
        <dl className="grid gap-3">
          {rows.map((row) => (
            <div
              className="grid gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm sm:grid-cols-[11rem_1fr]"
              key={row.label}
            >
              <dt className="flex items-center gap-2 text-slate-500">
                {row.required ? (
                  <AlertCircle className="size-4 text-amber-500" aria-hidden="true" />
                ) : (
                  <CheckCircle2 className="size-4 text-emerald-600" aria-hidden="true" />
                )}
                {row.label}
              </dt>
              <dd
                className={cn(
                  "font-medium text-slate-950",
                  row.required && "text-amber-700",
                )}
              >
                {row.value}
              </dd>
            </div>
          ))}
        </dl>
      </WizardFieldCard>
    </StepSection>
  );
}

function StepSection({
  children,
  description,
  icon: Icon,
  title,
}: {
  children: React.ReactNode;
  description: string;
  icon: LucideIcon;
  title: string;
}) {
  return (
    <section className="space-y-5">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-2xl bg-violet-50 text-violet-700">
          <Icon className="size-4" aria-hidden="true" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
          <p className="mt-1 text-sm leading-6 text-slate-600">{description}</p>
        </div>
      </div>
      {children}
    </section>
  );
}

function WizardFieldCard({
  children,
  title,
}: {
  children: React.ReactNode;
  title?: string;
}) {
  return (
    <motion.div
      animate={{ opacity: 1, y: 0 }}
      className="space-y-5 rounded-[1.35rem] border border-slate-200 bg-slate-50/55 p-4 shadow-sm sm:p-5"
      initial={{ opacity: 0, y: 8 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
    >
      {title ? <h3 className="text-sm font-semibold text-slate-950">{title}</h3> : null}
      {children}
    </motion.div>
  );
}

function PlotIllustration() {
  return (
    <div className="relative overflow-hidden rounded-[1.35rem] border border-blue-100 bg-gradient-to-br from-white via-blue-50/70 to-violet-50/70 p-5 shadow-sm">
      <div className="compose-project-plot-card" aria-hidden="true">
        <div className="compose-project-plot-shape">
          <span />
          <span />
          <span />
        </div>
        <div className="compose-project-road">
          <ArrowRight className="size-4" aria-hidden="true" />
        </div>
      </div>
      <div className="relative z-10 mt-5">
        <p className="text-sm font-semibold text-slate-950">Boundary reserved</p>
        <p className="mt-1 text-xs leading-5 text-slate-600">
          Plot drawing and exact geometry are handled later by Plot Intelligence, without changing
          this project record.
        </p>
      </div>
    </div>
  );
}

function DirectionSelect({
  id,
  registration,
}: {
  id: string;
  registration: UseFormRegisterReturn;
}) {
  return (
    <Select id={id} {...registration}>
      <option value="">Select direction</option>
      {["north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"].map(
        (direction) => (
          <option key={direction} value={direction}>
            {formatLabel(direction)}
          </option>
        ),
      )}
    </Select>
  );
}

function WizardSkeleton() {
  return (
    <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
      <Skeleton className="h-72 w-full" />
      <Skeleton className="h-[620px] w-full" />
    </div>
  );
}
