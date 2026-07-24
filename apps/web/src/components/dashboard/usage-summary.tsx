"use client";

import { Database, FolderKanban, Sparkles, View } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";

import { AccountSummaryError, AccountSummarySkeleton } from "@/components/dashboard/account-state";
import type { DashboardAccountState } from "@/components/dashboard/dashboard-types";
import { Progress } from "@/components/ui/progress";
import { SectionHeader } from "@/components/ui/section-header";
import { useProjectSummary } from "@/hooks/use-projects";

interface UsageSummaryProps {
  accountState: DashboardAccountState;
  onRetry: () => void;
}

const numberFormatter = new Intl.NumberFormat("en-US");

export function UsageSummary({ accountState, onRetry }: UsageSummaryProps) {
  const projectSummary = useProjectSummary();
  const reduceMotion = useReducedMotion();

  return (
    <section
      aria-labelledby="usage-summary-title"
      className="rounded-[1.5rem] border border-white/80 bg-white/90 p-5 shadow-[0_18px_55px_rgba(51,65,85,0.08)] backdrop-blur-xl"
    >
      <SectionHeader
        description="Current workspace allocation"
        title="Usage summary"
        titleId="usage-summary-title"
      />

      <div className="mt-5">
        {accountState.status === "loading" ? <AccountSummarySkeleton rows={4} /> : null}
        {accountState.status === "error" ? <AccountSummaryError onRetry={onRetry} /> : null}
        {accountState.status === "ready" ? (
          <div className="space-y-5">
            {[
              {
                icon: FolderKanban,
                label: "Projects",
                limit: accountState.context.subscription.projectLimit,
                value: projectSummary.data?.usedProjectSlots ?? 0,
                valueLabel: projectSummary.isError
                  ? "Unavailable"
                  : projectSummary.isLoading
                    ? "Loading"
                    : `${numberFormatter.format(projectSummary.data?.usedProjectSlots ?? 0)} / ${numberFormatter.format(accountState.context.subscription.projectLimit)}`,
              },
              {
                icon: Sparkles,
                label: "AI credits",
                limit: accountState.context.subscription.aiCreditLimit,
                value: 0,
                valueLabel: `0 / ${numberFormatter.format(accountState.context.subscription.aiCreditLimit)}`,
              },
              {
                icon: View,
                label: "3D renders",
                limit: accountState.context.subscription.renderLimit,
                value: 0,
                valueLabel: `0 / ${numberFormatter.format(accountState.context.subscription.renderLimit)}`,
              },
              {
                icon: Database,
                label: "Storage",
                limit: accountState.context.subscription.storageLimitMb,
                value: 0,
                valueLabel: `0 MB / ${numberFormatter.format(accountState.context.subscription.storageLimitMb)} MB`,
              },
            ].map((metric, index) => {
              const Icon = metric.icon;
              return (
              <motion.div
                animate={{ opacity: 1, y: 0 }}
                className="space-y-2"
                initial={{ opacity: 0, y: reduceMotion ? 0 : 5 }}
                key={metric.label}
                transition={{
                  delay: reduceMotion ? 0 : index * 0.03,
                  duration: reduceMotion ? 0 : 0.18,
                  ease: "easeOut",
                }}
              >
                <div className="flex items-center justify-between gap-4 text-sm">
                  <span className="flex min-w-0 items-center gap-2 text-slate-600">
                    <Icon className="size-4 shrink-0 text-violet-500" aria-hidden="true" />
                    {metric.label}
                  </span>
                  <span className="shrink-0 font-medium tabular-nums text-slate-950">
                    {metric.valueLabel}
                  </span>
                </div>
                <Progress label={`${metric.label} usage`} max={metric.limit} value={metric.value} />
              </motion.div>
            );
            })}
          </div>
        ) : null}
      </div>
    </section>
  );
}
