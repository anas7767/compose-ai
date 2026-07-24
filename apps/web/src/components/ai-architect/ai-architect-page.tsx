"use client";

import { useAuth } from "@clerk/nextjs";
import type {
  AIMessage,
  AIMessageMode,
  AIProposal,
  AISuggestedPrompt,
  AIThread,
} from "@compose-ai/shared";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  Bot,
  CircleCheck,
  FileCheck2,
  MessagesSquare,
  X,
} from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import Link from "next/link";
import * as React from "react";

import { BriefReviewPanel } from "@/components/ai-architect/brief-review-panel";
import { ChatPanel } from "@/components/ai-architect/chat-panel";
import { ConversationSidebar } from "@/components/ai-architect/conversation-sidebar";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import {
  requireSessionToken,
  useAIMemory,
  useAIMessages,
  useAIRun,
  useAISuggestedPrompts,
  useAIThreads,
  useAIUsage,
  useCurrentAIBrief,
} from "@/hooks/use-ai-architect";
import { useProjectDetail } from "@/hooks/use-projects";
import {
  applyAIProposals,
  archiveAIThread,
  cancelAIRun,
  createAIThread,
  generateAIBrief,
  reviewAIBrief,
  reviewAIProposal,
  sendAIMessage,
  streamAIRun,
} from "@/lib/api/ai-architect";
import { cn } from "@/lib/utils";

type MobileView = "threads" | "chat" | "brief";

interface AIArchitectPageProps {
  projectId: string;
}

export function AIArchitectPage({ projectId }: AIArchitectPageProps) {
  const { getToken, userId } = useAuth();
  const queryClient = useQueryClient();
  const reducedMotion = useReducedMotion();
  const project = useProjectDetail(projectId);
  const threads = useAIThreads(projectId);
  const brief = useCurrentAIBrief(projectId);
  const memory = useAIMemory(projectId);
  const usage = useAIUsage(projectId);
  const suggestions = useAISuggestedPrompts(projectId);
  const [selectedThreadId, setSelectedThreadId] = React.useState<string | null>(null);
  const messages = useAIMessages(projectId, selectedThreadId);
  const [mobileView, setMobileView] = React.useState<MobileView>("chat");
  const [mode, setMode] = React.useState<AIMessageMode>("advice");
  const [draft, setDraft] = React.useState("");
  const [rawRequirements, setRawRequirements] = React.useState("");
  const [sending, setSending] = React.useState(false);
  const [streamingContent, setStreamingContent] = React.useState("");
  const [activeRunId, setActiveRunId] = React.useState<string | null>(null);
  const [briefRunId, setBriefRunId] = React.useState<string | null>(null);
  const briefRun = useAIRun(projectId, briefRunId);
  const [busy, setBusy] = React.useState(false);
  const [actionError, setActionError] = React.useState<string | null>(null);
  const [selectedProposalIds, setSelectedProposalIds] = React.useState<Set<string>>(new Set());
  const streamController = React.useRef<AbortController | null>(null);
  const handledBriefRun = React.useRef<string | null>(null);
  const rawRecoveryLoaded = React.useRef(false);

  const archived = project.data?.status === "archived";
  const draftStorageKey = userId
    ? `compose:ai:draft:${userId}:${projectId}:${selectedThreadId ?? "new"}`
    : null;
  const rawStorageKey = userId ? `compose:ai:brief:${userId}:${projectId}` : null;

  React.useEffect(() => {
    const available = threads.data ?? [];
    if (!available.length) {
      setSelectedThreadId(null);
      return;
    }
    if (!selectedThreadId || !available.some((thread) => thread.id === selectedThreadId)) {
      setSelectedThreadId(available[0].id);
    }
  }, [selectedThreadId, threads.data]);

  React.useEffect(() => {
    if (!draftStorageKey) return;
    setDraft(window.localStorage.getItem(draftStorageKey) ?? "");
  }, [draftStorageKey]);

  React.useEffect(() => {
    if (!rawStorageKey || rawRecoveryLoaded.current) return;
    setRawRequirements(window.localStorage.getItem(rawStorageKey) ?? "");
    rawRecoveryLoaded.current = true;
  }, [rawStorageKey]);

  React.useEffect(() => {
    const run = briefRun.data;
    if (!run || handledBriefRun.current === run.id) return;
    if (run.status === "completed") {
      handledBriefRun.current = run.id;
      void Promise.all([
        queryClient.invalidateQueries({ queryKey: ["ai", projectId, "brief"] }),
        queryClient.invalidateQueries({ queryKey: ["ai", projectId, "memory"] }),
        queryClient.invalidateQueries({ queryKey: ["ai", projectId, "usage"] }),
      ]);
      setBriefRunId(null);
    }
    if (run.status === "failed" || run.status === "cancelled") {
      handledBriefRun.current = run.id;
      setActionError(
        run.failureCode
          ? `Brief generation stopped: ${run.failureCode.replaceAll("_", " ").toLowerCase()}.`
          : "Brief generation did not complete.",
      );
      setBriefRunId(null);
    }
  }, [briefRun.data, projectId, queryClient]);

  React.useEffect(() => {
    const approvedIds = new Set(
      brief.data?.proposals
        .filter((proposal) => proposal.status === "approved")
        .map((proposal) => proposal.id) ?? [],
    );
    setSelectedProposalIds((current) =>
      new Set([...current].filter((proposalId) => approvedIds.has(proposalId))),
    );
  }, [brief.data]);

  React.useEffect(() => {
    return () => streamController.current?.abort();
  }, []);

  const writeDraft = React.useCallback(
    (value: string) => {
      setDraft(value);
      if (!draftStorageKey) return;
      if (value) window.localStorage.setItem(draftStorageKey, value);
      else window.localStorage.removeItem(draftStorageKey);
    },
    [draftStorageKey],
  );

  const writeRawRequirements = React.useCallback(
    (value: string) => {
      setRawRequirements(value);
      if (!rawStorageKey) return;
      if (value) window.localStorage.setItem(rawStorageKey, value);
      else window.localStorage.removeItem(rawStorageKey);
    },
    [rawStorageKey],
  );

  const createConversation = React.useCallback(async (): Promise<AIThread | null> => {
    setBusy(true);
    setActionError(null);
    try {
      const token = await requireSessionToken(getToken);
      const created = await createAIThread(token, projectId, {}, crypto.randomUUID());
      queryClient.setQueryData<AIThread[]>(["ai", projectId, "threads"], (current = []) => [
        created,
        ...current,
      ]);
      setSelectedThreadId(created.id);
      setMobileView("chat");
      return created;
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Conversation could not be created.");
      return null;
    } finally {
      setBusy(false);
    }
  }, [getToken, projectId, queryClient]);

  const send = React.useCallback(async () => {
    const content = draft.trim();
    if (!content || sending || archived) return;
    setSending(true);
    setStreamingContent("");
    setActionError(null);
    let threadId = selectedThreadId;
    try {
      if (!threadId) {
        const created = await createConversation();
        if (!created) return;
        threadId = created.id;
      }
      const token = await requireSessionToken(getToken);
      const clientMessageId = crypto.randomUUID();
      const accepted = await sendAIMessage(
        token,
        projectId,
        threadId,
        { clientMessageId, content, mode },
        clientMessageId,
      );
      if (draftStorageKey) window.localStorage.removeItem(draftStorageKey);
      setDraft("");
      queryClient.setQueryData<AIMessage[]>(
        ["ai", projectId, "threads", threadId, "messages"],
        (current = []) => [...current, accepted.message],
      );
      setActiveRunId(accepted.run.id);
      const controller = new AbortController();
      streamController.current = controller;
      await streamAIRun(
        token,
        projectId,
        accepted.run.id,
        (event) => {
          if (event.eventType === "message.delta" && typeof event.payload.delta === "string") {
            setStreamingContent((current) => current + event.payload.delta);
          }
          if (event.eventType === "run.failed") {
            const code = typeof event.payload.code === "string" ? event.payload.code : "AI_RUN_FAILED";
            setActionError(`AI Architect could not complete the response (${code}).`);
          }
        },
        controller.signal,
      );
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) {
        setActionError(error instanceof Error ? error.message : "AI Architect could not respond.");
      }
    } finally {
      streamController.current = null;
      setSending(false);
      setStreamingContent("");
      setActiveRunId(null);
      if (threadId) {
        await queryClient.invalidateQueries({
          queryKey: ["ai", projectId, "threads", threadId, "messages"],
        });
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["ai", projectId, "threads"] }),
        queryClient.invalidateQueries({ queryKey: ["ai", projectId, "usage"] }),
      ]);
    }
  }, [
    archived,
    createConversation,
    draft,
    draftStorageKey,
    getToken,
    mode,
    projectId,
    queryClient,
    selectedThreadId,
    sending,
  ]);

  const stop = React.useCallback(async () => {
    streamController.current?.abort();
    if (!activeRunId) return;
    try {
      await cancelAIRun(await requireSessionToken(getToken), projectId, activeRunId);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "The AI run could not be stopped.");
    }
  }, [activeRunId, getToken, projectId]);

  const generateBrief = React.useCallback(async () => {
    if (rawRequirements.trim().length < 10 || archived) return;
    setBusy(true);
    setActionError(null);
    try {
      const accepted = await generateAIBrief(
        await requireSessionToken(getToken),
        projectId,
        { rawRequirements: rawRequirements.trim(), threadId: selectedThreadId },
        crypto.randomUUID(),
      );
      handledBriefRun.current = null;
      setBriefRunId(accepted.run.id);
      if (rawStorageKey) window.localStorage.removeItem(rawStorageKey);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Brief generation could not start.");
    } finally {
      setBusy(false);
    }
  }, [archived, getToken, projectId, rawRequirements, rawStorageKey, selectedThreadId]);

  const decideBrief = React.useCallback(
    async (decision: "approve" | "reject") => {
      if (!brief.data) return;
      setBusy(true);
      setActionError(null);
      try {
        const updated = await reviewAIBrief(
          await requireSessionToken(getToken),
          projectId,
          brief.data.id,
          decision,
          crypto.randomUUID(),
        );
        queryClient.setQueryData(["ai", projectId, "brief", "current"], updated);
      } catch (error) {
        setActionError(error instanceof Error ? error.message : "Brief review could not be saved.");
      } finally {
        setBusy(false);
      }
    },
    [brief.data, getToken, projectId, queryClient],
  );

  const decideProposal = React.useCallback(
    async (proposal: AIProposal, decision: "approve" | "reject") => {
      setBusy(true);
      setActionError(null);
      try {
        await reviewAIProposal(
          await requireSessionToken(getToken),
          projectId,
          proposal.id,
          decision,
          crypto.randomUUID(),
        );
        await queryClient.invalidateQueries({ queryKey: ["ai", projectId, "brief"] });
      } catch (error) {
        setActionError(error instanceof Error ? error.message : "Proposal review could not be saved.");
      } finally {
        setBusy(false);
      }
    },
    [getToken, projectId, queryClient],
  );

  const applySelected = React.useCallback(async () => {
    if (!project.data || !selectedProposalIds.size) return;
    setBusy(true);
    setActionError(null);
    try {
      await applyAIProposals(
        await requireSessionToken(getToken),
        projectId,
        project.data.version,
        [...selectedProposalIds],
        crypto.randomUUID(),
      );
      setSelectedProposalIds(new Set());
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["projects"] }),
        queryClient.invalidateQueries({ queryKey: ["ai", projectId, "brief"] }),
        queryClient.invalidateQueries({ queryKey: ["ai", projectId, "memory"] }),
      ]);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Approved changes could not be applied.");
    } finally {
      setBusy(false);
    }
  }, [getToken, project.data, projectId, queryClient, selectedProposalIds]);

  const archiveConversation = React.useCallback(
    async (thread: AIThread) => {
      setBusy(true);
      setActionError(null);
      try {
        await archiveAIThread(
          await requireSessionToken(getToken),
          projectId,
          thread.id,
        );
        await queryClient.invalidateQueries({ queryKey: ["ai", projectId, "threads"] });
      } catch (error) {
        setActionError(error instanceof Error ? error.message : "Conversation could not be archived.");
      } finally {
        setBusy(false);
      }
    },
    [getToken, projectId, queryClient],
  );

  const usePrompt = React.useCallback(
    (prompt: AISuggestedPrompt) => {
      setMode(prompt.mode);
      writeDraft(prompt.prompt);
    },
    [writeDraft],
  );

  if (project.isLoading) return <AIArchitectSkeleton />;
  if (project.isError || !project.data) {
    return (
      <div className="compose-architect-light -mx-4 -my-6 flex min-h-[calc(100dvh-4rem)] items-center justify-center px-4 sm:-mx-6 sm:px-6 lg:-mx-8 lg:-my-8 lg:px-8">
        <EmptyState
          action={<Button onClick={() => project.refetch()}>Retry</Button>}
          className="w-full max-w-xl rounded-lg border border-border bg-card shadow-sm"
          description="Compose could not load the project context required by AI Architect."
          icon={Bot}
          title="AI Architect unavailable"
        />
      </div>
    );
  }

  const generating = Boolean(briefRunId) || (busy && !brief.data);
  return (
    <div className="compose-architect-light -mx-4 -my-6 min-h-[calc(100dvh-4rem)] bg-[#f7f8fb] px-4 py-5 sm:-mx-6 sm:px-6 lg:-mx-8 lg:-my-8 lg:px-6 lg:py-6">
      <div className="mx-auto w-full max-w-[1380px] space-y-4">
        <header className="flex flex-col gap-4 border-b border-slate-200 pb-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <Button asChild className="-ml-3 text-slate-500" size="sm" variant="ghost">
              <Link href={`/projects/${projectId}`}>
                <ArrowLeft aria-hidden="true" />
                Project
              </Link>
            </Button>
            <div className="mt-2 flex items-center gap-3">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-md border border-violet-200 bg-white text-violet-700 shadow-sm">
                <Bot aria-hidden="true" className="size-[18px]" />
              </span>
              <div className="min-w-0">
                <h1 className="text-xl font-semibold text-slate-950">AI Architect</h1>
                <p className="mt-0.5 truncate text-sm text-slate-500">
                  {project.data.name} · Requirement brief and project decisions
                </p>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-slate-500">
            <span className="inline-flex items-center gap-1.5">
              <CircleCheck aria-hidden="true" className="size-3.5 text-emerald-600" />
              Project context loaded
            </span>
            {brief.data ? (
              <span>
                Brief v{brief.data.version} · {brief.data.status.replaceAll("_", " ")}
              </span>
            ) : null}
            {archived ? (
              <span className="rounded-md border border-amber-200 bg-amber-50 px-2.5 py-1.5 font-medium text-amber-700">
                Archived · Read-only
              </span>
            ) : null}
          </div>
        </header>

        <AnimatePresence initial={false}>
          {actionError ? (
            <motion.div
              animate={{ opacity: 1, y: 0 }}
              className="flex items-start gap-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-700"
              exit={reducedMotion ? undefined : { opacity: 0, y: -4 }}
              initial={reducedMotion ? false : { opacity: 0, y: -4 }}
              key="architect-error"
              role="alert"
            >
              <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              <p className="min-w-0 flex-1 leading-5">{actionError}</p>
              <button
                aria-label="Dismiss error"
                className="flex size-7 shrink-0 items-center justify-center rounded-md text-rose-600 outline-none transition-colors hover:bg-rose-100 focus-visible:ring-2 focus-visible:ring-rose-400"
                onClick={() => setActionError(null)}
                type="button"
              >
                <X aria-hidden="true" className="size-3.5" />
              </button>
            </motion.div>
          ) : null}
        </AnimatePresence>

        <MobileViewSwitcher onChange={setMobileView} value={mobileView} />

        <div className="compose-architect-frame overflow-hidden rounded-lg border border-slate-200 bg-white xl:grid xl:grid-cols-[240px_minmax(0,1fr)] 2xl:grid-cols-[240px_minmax(420px,1fr)_400px]">
          <div
            className={cn(
              "min-w-0",
              mobileView !== "threads" && "hidden",
              "xl:block",
              mobileView === "threads" && "compose-architect-panel-active",
            )}
          >
          <ConversationSidebar
            activeThreadId={selectedThreadId}
            archived={archived}
            busy={busy}
            loading={threads.isLoading}
            onArchive={(thread) => void archiveConversation(thread)}
            onCreate={() => void createConversation()}
            onSelect={(threadId) => {
              setSelectedThreadId(threadId);
              setMobileView("chat");
            }}
            threads={threads.data ?? []}
          />
          </div>
          <div
            className={cn(
              "min-w-0",
              mobileView !== "chat" && "hidden",
              mobileView === "brief" ? "xl:hidden" : "xl:block",
              "2xl:block",
              mobileView === "chat" && "compose-architect-panel-active",
            )}
          >
          <ChatPanel
            archived={archived}
            draft={draft}
            loading={messages.isLoading}
            messages={messages.data ?? []}
            mode={mode}
            onDraftChange={writeDraft}
            onModeChange={setMode}
            onSend={() => void send()}
            onStop={() => void stop()}
            onUsePrompt={usePrompt}
            sending={sending}
            streamingContent={streamingContent}
            suggestions={suggestions.data ?? []}
            threadSelected={Boolean(selectedThreadId)}
          />
          </div>
          <div
            className={cn(
              "min-w-0",
              mobileView !== "brief" && "hidden",
              mobileView === "brief" ? "xl:block" : "xl:hidden",
              "2xl:block",
              mobileView === "brief" && "compose-architect-panel-active",
            )}
          >
          <BriefReviewPanel
            archived={archived}
            brief={brief.data}
            busy={busy}
            generating={generating}
            loading={brief.isLoading}
            memory={memory.data}
            onApply={() => void applySelected()}
            onBriefDecision={(decision) => void decideBrief(decision)}
            onGenerate={() => void generateBrief()}
            onProposalDecision={(proposal, decision) => void decideProposal(proposal, decision)}
            onRawRequirementsChange={writeRawRequirements}
            onToggleProposal={(proposalId) =>
              setSelectedProposalIds((current) => {
                const next = new Set(current);
                if (next.has(proposalId)) next.delete(proposalId);
                else next.add(proposalId);
                return next;
              })
            }
            rawRequirements={rawRequirements}
            selectedProposalIds={selectedProposalIds}
            usage={usage.data}
          />
          </div>
        </div>
      </div>
    </div>
  );
}

function MobileViewSwitcher({
  onChange,
  value,
}: {
  onChange: (value: MobileView) => void;
  value: MobileView;
}) {
  const reducedMotion = useReducedMotion();
  const items = [
    { value: "threads" as const, label: "Threads", icon: MessagesSquare },
    { value: "chat" as const, label: "Chat", icon: Bot },
    { value: "brief" as const, label: "Review", icon: FileCheck2 },
  ];
  return (
    <div
      aria-label="AI Architect workspace views"
      className="grid grid-cols-3 rounded-md border border-slate-200 bg-slate-100 p-1 xl:grid-cols-2 2xl:hidden"
      role="group"
    >
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <button
            aria-pressed={value === item.value}
            className={cn(
              "relative flex h-10 items-center justify-center gap-2 rounded-md text-xs font-medium text-slate-500 outline-none transition-colors focus-visible:ring-2 focus-visible:ring-violet-500/50",
              item.value === "threads" && "xl:hidden",
              value === item.value && "text-slate-950",
            )}
            key={item.value}
            onClick={() => onChange(item.value)}
            type="button"
          >
            {value === item.value ? (
              <motion.span
                className="absolute inset-0 rounded-md border border-slate-200 bg-white shadow-sm"
                layoutId={reducedMotion ? undefined : "architect-workspace-view"}
                transition={
                  reducedMotion
                    ? { duration: 0 }
                    : { bounce: 0, duration: 0.2, type: "spring" }
                }
              />
            ) : null}
            <Icon aria-hidden="true" className="relative z-10 size-4" />
            <span className="relative z-10">{item.label}</span>
          </button>
        );
      })}
    </div>
  );
}

function AIArchitectSkeleton() {
  return (
    <div className="compose-architect-light -mx-4 -my-6 min-h-[calc(100dvh-4rem)] bg-[#f7f8fb] px-4 py-5 sm:-mx-6 sm:px-6 lg:-mx-8 lg:-my-8 lg:px-6 lg:py-6">
      <div className="mx-auto w-full max-w-[1380px] space-y-4">
        <div className="flex h-20 items-center gap-3 border-b border-slate-200">
          <Skeleton className="size-9 bg-slate-200" />
          <div className="space-y-2">
            <Skeleton className="h-5 w-36 bg-slate-200" />
            <Skeleton className="h-3 w-64 max-w-[70vw] bg-slate-200" />
          </div>
        </div>
        <div className="compose-architect-frame grid gap-px overflow-hidden rounded-lg border border-slate-200 bg-slate-200 xl:grid-cols-[240px_minmax(0,1fr)] 2xl:grid-cols-[240px_minmax(420px,1fr)_400px]">
          <Skeleton className="h-[680px] rounded-none bg-white" />
          <Skeleton className="hidden h-[680px] rounded-none bg-white xl:block" />
          <Skeleton className="hidden h-[680px] rounded-none bg-white 2xl:block" />
        </div>
      </div>
    </div>
  );
}
