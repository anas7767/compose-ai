"use client";

import type {
  AIBrief,
  AIMemory,
  AIProposal,
  AISourceReference,
  AIUsage,
} from "@compose-ai/shared";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  CircleHelp,
  FileText,
  Info,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  X,
} from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import * as React from "react";

import {
  ConfidenceIndicator,
  SourceReferences,
} from "@/components/ai-architect/review-indicators";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

type ReviewView = "brief" | "review" | "context";

interface BriefReviewPanelProps {
  archived: boolean;
  brief: AIBrief | null | undefined;
  busy: boolean;
  generating: boolean;
  loading: boolean;
  memory: AIMemory | null | undefined;
  onApply: () => void;
  onBriefDecision: (decision: "approve" | "reject") => void;
  onGenerate: () => void;
  onProposalDecision: (proposal: AIProposal, decision: "approve" | "reject") => void;
  onRawRequirementsChange: (value: string) => void;
  onToggleProposal: (proposalId: string) => void;
  rawRequirements: string;
  selectedProposalIds: Set<string>;
  usage: AIUsage | undefined;
}

export function BriefReviewPanel({
  archived,
  brief,
  busy,
  generating,
  loading,
  memory,
  onApply,
  onBriefDecision,
  onGenerate,
  onProposalDecision,
  onRawRequirementsChange,
  onToggleProposal,
  rawRequirements,
  selectedProposalIds,
  usage,
}: BriefReviewPanelProps) {
  const [view, setView] = React.useState<ReviewView>(brief ? "brief" : "review");
  const reducedMotion = useReducedMotion();

  React.useEffect(() => {
    if (brief) setView("brief");
  }, [brief?.id]);

  return (
    <aside className="flex min-h-[660px] min-w-0 flex-col border-l border-slate-200 bg-[#fbfcfe] xl:h-[max(620px,calc(100dvh-13rem))] xl:min-h-0 xl:max-h-[840px]">
      <div className="border-b border-slate-200 bg-white px-4 py-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-slate-900">Brief review</h2>
            <p className="mt-0.5 truncate text-xs text-slate-500">
              {brief ? `Version ${brief.version} | ${formatLabel(brief.status)}` : "Not generated"}
            </p>
          </div>
          {brief ? <ConfidenceIndicator value={brief.aggregateConfidence} /> : null}
        </div>
        <div
          aria-label="Brief panel view"
          className="mt-3 grid grid-cols-3 rounded-md border border-slate-200 bg-slate-100 p-0.5"
          role="group"
        >
          {(["brief", "review", "context"] as const).map((item) => (
            <button
              aria-pressed={view === item}
              className={cn(
                "relative h-8 rounded text-xs font-medium capitalize text-slate-500 outline-none focus-visible:ring-2 focus-visible:ring-violet-500/50",
                view === item && "text-slate-900",
              )}
              key={item}
              onClick={() => setView(item)}
              type="button"
            >
              {view === item ? (
                <motion.span
                  className="absolute inset-0 rounded border border-slate-200 bg-white shadow-sm"
                  layoutId={reducedMotion ? undefined : "architect-review-view"}
                  transition={
                    reducedMotion
                      ? { duration: 0 }
                      : { bounce: 0, duration: 0.2, type: "spring" }
                  }
                />
              ) : null}
              <span className="relative z-10">{item}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto" data-architect-scroll>
        {loading ? <BriefPanelSkeleton /> : null}
        {!loading ? (
          <AnimatePresence initial={false} mode="wait">
            <motion.div
              animate={{ opacity: 1, x: 0 }}
              exit={reducedMotion ? undefined : { opacity: 0, x: -5 }}
              initial={reducedMotion ? false : { opacity: 0, x: 5 }}
              key={view}
              transition={{ duration: 0.18 }}
            >
              {view === "brief" ? (
                <BriefView
                  archived={archived}
                  brief={brief}
                  busy={busy}
                  onBriefDecision={onBriefDecision}
                />
              ) : null}
              {view === "review" ? (
                <ReviewViewPanel
                  archived={archived}
                  brief={brief}
                  busy={busy}
                  generating={generating}
                  onApply={onApply}
                  onGenerate={onGenerate}
                  onProposalDecision={onProposalDecision}
                  onRawRequirementsChange={onRawRequirementsChange}
                  onToggleProposal={onToggleProposal}
                  rawRequirements={rawRequirements}
                  selectedProposalIds={selectedProposalIds}
                />
              ) : null}
              {view === "context" ? <ContextView memory={memory} usage={usage} /> : null}
            </motion.div>
          </AnimatePresence>
        ) : null}
      </div>
    </aside>
  );
}

function BriefView({
  archived,
  brief,
  busy,
  onBriefDecision,
}: {
  archived: boolean;
  brief: AIBrief | null | undefined;
  busy: boolean;
  onBriefDecision: (decision: "approve" | "reject") => void;
}) {
  if (!brief) {
    return (
      <div className="px-5 py-14 text-center">
        <span className="mx-auto flex size-10 items-center justify-center rounded-md border border-violet-100 bg-violet-50 text-violet-700">
          <FileText aria-hidden="true" className="size-[18px]" />
        </span>
        <h3 className="mt-4 text-sm font-semibold text-slate-900">No structured brief yet</h3>
        <p className="mt-2 text-xs leading-5 text-slate-500">
          Open Review, add the client requirements, and generate the first version.
        </p>
      </div>
    );
  }
  return (
    <div className="divide-y divide-slate-200">
      <BriefSection title="Summary">
        <p className="text-sm leading-6 text-slate-700">{brief.summary}</p>
      </BriefSection>
      <BriefSection count={brief.goals.length} title="Goals">
        <BriefList items={brief.goals} />
      </BriefSection>
      <BriefSection count={brief.priorities.length} title="Priorities">
        <BriefList items={brief.priorities} />
      </BriefSection>
      <BriefSection count={brief.constraints.length} title="Constraints">
        <BriefList items={brief.constraints} />
      </BriefSection>
      <BriefSection count={brief.missingInformation.length} title="Missing information">
        {brief.missingInformation.length ? (
          <ul className="divide-y divide-slate-100">
            {brief.missingInformation.map((item) => (
              <li className="py-3 first:pt-0 last:pb-0" key={`${item.topic}-${item.reason}`}>
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md bg-amber-50 text-amber-700">
                    <CircleHelp aria-hidden="true" className="size-3.5" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-medium text-slate-800">{item.topic}</p>
                      {item.blocking ? (
                        <Badge className="h-5 rounded border-amber-200 bg-amber-50 text-amber-700">
                          Blocking
                        </Badge>
                      ) : null}
                      <span className="text-[11px] capitalize text-slate-400">{item.priority}</span>
                    </div>
                    <p className="mt-1 text-xs leading-5 text-slate-500">{item.reason}</p>
                    <p className="mt-1.5 text-xs leading-5 text-slate-600">
                      <span className="font-medium">Needed:</span> {item.expected_answer}
                    </p>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <ResolvedState label="No missing information identified" />
        )}
      </BriefSection>
      <BriefSection count={brief.conflicts.length} title="Conflicts">
        {brief.conflicts.length ? (
          <ul className="space-y-3">
            {brief.conflicts.map((conflict) => (
              <li
                className="rounded-md border border-rose-200 bg-rose-50/60 p-3.5"
                key={conflict.title}
              >
                <div className="flex items-start gap-2.5">
                  <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-rose-600" />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-medium text-slate-800">{conflict.title}</p>
                      <Badge className="h-5 rounded capitalize" variant="outline">
                        {conflict.severity}
                      </Badge>
                    </div>
                    <p className="mt-2 text-xs leading-5 text-slate-600">
                      {conflict.description}
                    </p>
                    <div className="mt-2 flex gap-2 text-xs leading-5 text-slate-700">
                      <ArrowRight aria-hidden="true" className="mt-0.5 size-3.5 shrink-0 text-violet-600" />
                      <p>{conflict.suggested_resolution}</p>
                    </div>
                    {conflict.affected_paths.length ? (
                      <p className="mt-2 break-words text-[11px] text-slate-500">
                        Affects {conflict.affected_paths.map(formatPath).join(", ")}
                      </p>
                    ) : null}
                    <SourceReferences sources={conflict.source_references} />
                  </div>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <ResolvedState label="No contradictions identified" />
        )}
      </BriefSection>
      <BriefSection count={brief.clarificationQuestions.length} title="Suggested questions">
        <ol className="space-y-3">
          {brief.clarificationQuestions.map((item) => (
            <li className="flex gap-3 text-sm" key={item.question}>
              <span className="flex size-6 shrink-0 items-center justify-center rounded-md bg-violet-50 text-violet-700">
                <CircleHelp aria-hidden="true" className="size-3.5" />
              </span>
              <div>
                <p className="font-medium leading-5 text-slate-800">{item.question}</p>
                <p className="mt-1 text-xs leading-5 text-slate-500">{item.reason}</p>
              </div>
            </li>
          ))}
        </ol>
      </BriefSection>
      <BriefSection count={brief.recommendedNextSteps.length} title="Recommended next steps">
        {brief.recommendedNextSteps.length ? (
          <ol className="space-y-3">
            {brief.recommendedNextSteps.map((step) => (
              <li className="flex gap-3" key={`${step.priority}-${step.title}`}>
                <span className="flex size-6 shrink-0 items-center justify-center rounded-md bg-blue-50 text-[11px] font-semibold text-blue-700">
                  {step.priority}
                </span>
                <div>
                  <p className="text-sm font-medium text-slate-800">{step.title}</p>
                  <p className="mt-1 text-xs leading-5 text-slate-500">{step.description}</p>
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-xs text-slate-500">No next steps recommended.</p>
        )}
      </BriefSection>
      {brief.assumptions.length || brief.warnings.length ? (
        <BriefSection title="Assumptions and warnings">
          <ul className="space-y-3">
            {brief.assumptions.map((assumption) => (
              <li className="flex gap-2.5 text-xs leading-5" key={assumption.statement}>
                <Info aria-hidden="true" className="mt-0.5 size-3.5 shrink-0 text-blue-600" />
                <div>
                  <p className="text-slate-700">{assumption.statement}</p>
                  <p className="mt-0.5 text-slate-500">{assumption.reason}</p>
                </div>
              </li>
            ))}
            {brief.warnings.map((warning) => (
              <li className="flex gap-2.5 text-xs leading-5" key={`${warning.code}-${warning.message}`}>
                <AlertTriangle aria-hidden="true" className="mt-0.5 size-3.5 shrink-0 text-amber-600" />
                <p className="text-slate-600">{warning.message}</p>
              </li>
            ))}
          </ul>
        </BriefSection>
      ) : null}
      <div className="sticky bottom-0 border-t border-slate-200 bg-white/95 p-4 backdrop-blur-lg">
        {brief.status === "proposed" || brief.status === "under_review" ? (
          <div className="grid grid-cols-2 gap-2">
            <Button
              disabled={archived || busy}
              onClick={() => onBriefDecision("reject")}
              variant="outline"
            >
              <X aria-hidden="true" />
              Reject
            </Button>
            <Button disabled={archived || busy} onClick={() => onBriefDecision("approve")}>
              <Check aria-hidden="true" />
              Approve brief
            </Button>
          </div>
        ) : (
          <p className="text-center text-xs text-slate-500">
            Brief status: {formatLabel(brief.status)}
          </p>
        )}
      </div>
    </div>
  );
}

function ReviewViewPanel({
  archived,
  brief,
  busy,
  generating,
  onApply,
  onGenerate,
  onProposalDecision,
  onRawRequirementsChange,
  onToggleProposal,
  rawRequirements,
  selectedProposalIds,
}: Omit<BriefReviewPanelProps, "loading" | "memory" | "onBriefDecision" | "usage">) {
  const approved = brief?.proposals.filter((item) => item.status === "approved") ?? [];
  return (
    <div className="divide-y divide-slate-200">
      <div className="p-4">
        <label className="text-sm font-semibold text-slate-900" htmlFor="raw-architect-requirements">
          Raw requirements
        </label>
        <p className="mt-1 text-xs leading-5 text-slate-500">
          Original text is preserved with every generated brief version.
        </p>
        <Textarea
          className="mt-3 min-h-40 border-slate-300 bg-white text-slate-800 shadow-sm placeholder:text-slate-400 focus-visible:border-violet-400 focus-visible:ring-violet-500/20"
          disabled={archived || generating}
          id="raw-architect-requirements"
          maxLength={30000}
          onChange={(event) => onRawRequirementsChange(event.target.value)}
          placeholder="Describe the client goals, room needs, budget, floors, parking, style, and site constraints..."
          value={rawRequirements}
        />
        <Button
          className="mt-3 w-full bg-violet-600 text-white hover:bg-violet-700"
          disabled={archived || generating || rawRequirements.trim().length < 10}
          onClick={onGenerate}
        >
          {generating ? (
            <LoaderCircle aria-hidden="true" className="animate-spin" />
          ) : (
            <RefreshCw aria-hidden="true" />
          )}
          {generating ? "Generating brief..." : brief ? "Generate new version" : "Generate brief"}
        </Button>
      </div>

      <div className="p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">Proposed changes</h3>
            <p className="mt-1 text-xs text-slate-500">
              Approve values individually before applying.
            </p>
          </div>
          <Badge className="rounded border-violet-200 bg-violet-50 text-violet-700">
            {brief?.proposals.length ?? 0}
          </Badge>
        </div>
        {brief?.proposals.length ? (
          <ul className="mt-4 space-y-3">
            {brief.proposals.map((proposal) => (
              <ProposalRow
                archived={archived}
                busy={busy}
                key={proposal.id}
                onDecision={onProposalDecision}
                onToggle={onToggleProposal}
                proposal={proposal}
                selected={selectedProposalIds.has(proposal.id)}
              />
            ))}
          </ul>
        ) : (
          <div className="mt-4 border-y border-dashed border-slate-200 px-3 py-7 text-center">
            <FileText aria-hidden="true" className="mx-auto size-4 text-slate-400" />
            <p className="mt-2 text-xs text-slate-500">
            {brief ? "No project changes were proposed." : "Generate a brief to review changes."}
            </p>
          </div>
        )}
      </div>

      {approved.length ? (
        <div className="sticky bottom-0 border-t border-slate-200 bg-white/95 p-4 backdrop-blur-lg">
          <Button
            className="w-full bg-violet-600 text-white hover:bg-violet-700"
            disabled={archived || busy || selectedProposalIds.size === 0}
            onClick={onApply}
          >
            <ShieldCheck aria-hidden="true" />
            Apply selected ({selectedProposalIds.size})
          </Button>
          <p className="mt-2 text-center text-xs text-slate-500">
            Current project version is checked again before application.
          </p>
        </div>
      ) : null}
    </div>
  );
}

function ProposalRow({
  archived,
  busy,
  onDecision,
  onToggle,
  proposal,
  selected,
}: {
  archived: boolean;
  busy: boolean;
  onDecision: (proposal: AIProposal, decision: "approve" | "reject") => void;
  onToggle: (proposalId: string) => void;
  proposal: AIProposal;
  selected: boolean;
}) {
  const blocked = proposal.warnings.some((warning) => warning.code === "BLOCKING_CONFLICT");
  return (
    <li className="rounded-lg border border-slate-200 bg-white p-3.5 shadow-[0_6px_18px_rgb(51_65_85_/_0.04)]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-xs font-medium text-slate-500">
            {formatPath(proposal.targetPath)}
          </p>
          <p className="mt-1 break-words text-sm font-semibold text-slate-900">
            {displayValue(proposal.proposedValue)}
          </p>
        </div>
        <ConfidenceIndicator value={proposal.confidence} />
      </div>
      <div className="mt-3 grid grid-cols-2 overflow-hidden rounded-md border border-slate-200 text-xs">
        <div className="min-w-0 bg-slate-50 p-2.5">
          <p className="text-slate-500">Current</p>
          <p className="mt-1 break-words text-slate-700">
            {displayValue(proposal.existingValue)}
          </p>
        </div>
        <div className="min-w-0 border-l border-slate-200 bg-violet-50/50 p-2.5">
          <p className="text-violet-600">Suggested</p>
          <p className="mt-1 break-words font-medium text-violet-800">
            {displayValue(proposal.proposedValue)}
          </p>
        </div>
      </div>
      <p className="mt-3 text-xs leading-5 text-slate-600">{proposal.explanation}</p>
      <SourceReferences sources={proposal.sourceReferences} />
      {proposal.warnings.length ? (
        <ul className="mt-3 space-y-1.5 border-t border-slate-200 pt-3">
          {proposal.warnings.map((warning) => (
            <li
              className="flex items-start gap-2 text-xs leading-5 text-amber-700"
              key={`${warning.code}-${warning.message}`}
            >
              <AlertTriangle aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
              <span>{warning.message}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {proposal.status === "pending" ? (
        <div className="mt-3 grid grid-cols-2 gap-2">
          <Button
            disabled={archived || busy}
            onClick={() => onDecision(proposal, "reject")}
            size="sm"
            variant="ghost"
          >
            <X aria-hidden="true" />
            Reject
          </Button>
          <Button
            className="border-violet-200 bg-violet-50 text-violet-700 hover:bg-violet-100"
            disabled={archived || busy || blocked}
            onClick={() => onDecision(proposal, "approve")}
            size="sm"
            variant="outline"
          >
            <Check aria-hidden="true" />
            Approve
          </Button>
        </div>
      ) : null}
      {proposal.status === "approved" ? (
        <label className="mt-3 flex min-h-10 cursor-pointer items-center gap-2 rounded-md bg-emerald-50 px-2.5 text-xs font-medium text-emerald-800">
          <input
            checked={selected}
            className="size-4 accent-emerald-600"
            disabled={archived || busy}
            onChange={() => onToggle(proposal.id)}
            type="checkbox"
          />
          Include when applying
        </label>
      ) : null}
      {proposal.status !== "pending" && proposal.status !== "approved" ? (
        <p className="mt-3 text-xs font-medium text-slate-500">
          {formatLabel(proposal.status)}
        </p>
      ) : null}
    </li>
  );
}

function ContextView({ memory, usage }: { memory: AIMemory | null | undefined; usage?: AIUsage }) {
  const monthlyPercent = usage?.monthlyCostLimitMicrousd
    ? Math.min(100, Math.round((usage.costMicrousd / usage.monthlyCostLimitMicrousd) * 100))
    : 0;
  return (
    <div className="divide-y divide-slate-200">
      <BriefSection title="Project memory">
        {memory ? (
          <dl className="space-y-3 text-xs">
            <ContextRow label="Memory version" value={String(memory.version)} />
            <ContextRow label="Project version" value={String(memory.projectVersion)} />
            <ContextRow label="Estimated tokens" value={memory.tokenEstimate.toLocaleString()} />
            <ContextRow label="Schema" value={memory.schemaVersion} />
            <ContextRow label="Included sources" value={String(memory.includedSources.length)} />
            <div className="pt-2">
              <dt className="text-slate-500">Summary</dt>
              <dd className="mt-1 leading-5 text-slate-700">{memory.contextSummary}</dd>
            </div>
          </dl>
        ) : (
          <p className="text-xs leading-5 text-slate-500">
            Project memory is created before the first AI run.
          </p>
        )}
      </BriefSection>
      <BriefSection title="Usage this month">
        {usage ? (
          <div>
            <div className="flex items-end justify-between gap-3">
              <div>
                <p className="text-xl font-semibold tabular-nums text-slate-900">
                  ${(usage.costMicrousd / 1_000_000).toFixed(4)}
                </p>
                <p className="mt-1 text-xs text-slate-500">Recorded provider cost</p>
              </div>
              <Badge className="rounded border-violet-200 bg-violet-50 text-violet-700">
                {usage.runCount} runs
              </Badge>
            </div>
            <Progress className="mt-4" label="Monthly AI cost usage" value={monthlyPercent} />
            <dl className="mt-4 space-y-3 text-xs">
              <ContextRow label="Input tokens" value={usage.inputTokens.toLocaleString()} />
              <ContextRow label="Output tokens" value={usage.outputTokens.toLocaleString()} />
              <ContextRow label="Cache hits" value={usage.cacheHitCount.toLocaleString()} />
              <ContextRow
                label="Monthly ceiling"
                value={`$${(usage.monthlyCostLimitMicrousd / 1_000_000).toFixed(2)}`}
              />
            </dl>
          </div>
        ) : (
          <Skeleton className="h-36 w-full" />
        )}
      </BriefSection>
      <BriefSection title="Safety controls">
        <ul className="space-y-3 text-xs leading-5 text-slate-500">
          <li className="flex gap-2">
            <ShieldCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-emerald-600" />
            Client contact details are excluded from model context by default.
          </li>
          <li className="flex gap-2">
            <ShieldCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-emerald-600" />
            Project updates require field-level approval and a current version match.
          </li>
        </ul>
      </BriefSection>
    </div>
  );
}

function BriefSection({
  children,
  count,
  title,
}: {
  children: React.ReactNode;
  count?: number;
  title: string;
}) {
  return (
    <section className="p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
        {count !== undefined ? (
          <span className="text-xs tabular-nums text-slate-400">{count}</span>
        ) : null}
      </div>
      {children}
    </section>
  );
}

function BriefList({
  items,
}: {
  items: Array<{
    title: string;
    description: string;
    confidence: number;
    source_references?: AISourceReference[];
  }>;
}) {
  if (!items.length) return <p className="text-xs text-slate-500">None identified.</p>;
  return (
    <ul className="divide-y divide-slate-100">
      {items.map((item) => (
        <li className="py-3 first:pt-0 last:pb-0" key={`${item.title}-${item.description}`}>
          <div className="flex items-start justify-between gap-3">
            <p className="text-sm font-medium text-slate-800">{item.title}</p>
            <ConfidenceIndicator value={item.confidence} />
          </div>
          <p className="mt-1 text-xs leading-5 text-slate-500">{item.description}</p>
          <SourceReferences sources={item.source_references ?? []} />
        </li>
      ))}
    </ul>
  );
}

function ResolvedState({ label }: { label: string }) {
  return (
    <p className="flex items-center gap-2 text-xs text-slate-500">
      <CheckCircle2 aria-hidden="true" className="size-4 text-emerald-600" />
      {label}
    </p>
  );
}

function ContextRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <dt className="text-slate-500">{label}</dt>
      <dd className="max-w-[60%] truncate text-right font-medium text-slate-700">{value}</dd>
    </div>
  );
}

function BriefPanelSkeleton() {
  return (
    <div className="space-y-4 p-4" role="status" aria-label="Loading brief review">
      <Skeleton className="h-24 w-full bg-slate-200" />
      <Skeleton className="h-44 w-full bg-slate-100" />
      <Skeleton className="h-36 w-full bg-slate-100" />
    </div>
  );
}

function formatLabel(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatPath(value: string): string {
  return value
    .replace(/^\//, "")
    .replaceAll("/", " / ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not specified";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "string" || typeof value === "number") return String(value);
  if (Array.isArray(value)) return `${value.length} ${value.length === 1 ? "item" : "items"}`;
  return JSON.stringify(value);
}
