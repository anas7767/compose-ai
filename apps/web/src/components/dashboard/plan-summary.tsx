import { Crown, ShieldCheck, UsersRound } from "lucide-react";

import { AccountSummaryError, AccountSummarySkeleton } from "@/components/dashboard/account-state";
import type { DashboardAccountState } from "@/components/dashboard/dashboard-types";
import { Badge } from "@/components/ui/badge";
import { SectionHeader } from "@/components/ui/section-header";

interface PlanSummaryProps {
  accountState: DashboardAccountState;
  onRetry: () => void;
}

function formatLabel(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function PlanSummary({ accountState, onRetry }: PlanSummaryProps) {
  return (
    <section
      aria-labelledby="plan-summary-title"
      className="rounded-[1.5rem] border border-white/80 bg-white/90 p-5 shadow-[0_18px_55px_rgba(51,65,85,0.08)] backdrop-blur-xl"
    >
      <SectionHeader title="Plan summary" titleId="plan-summary-title" />

      <div className="mt-5">
        {accountState.status === "loading" ? <AccountSummarySkeleton rows={3} /> : null}
        {accountState.status === "error" ? <AccountSummaryError onRetry={onRetry} /> : null}
        {accountState.status === "ready" ? (
          <div>
            <div className="rounded-2xl border border-violet-100 bg-gradient-to-br from-white to-violet-50/70 p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex min-w-0 items-start gap-3">
                  <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-violet-50 text-violet-700">
                    <Crown className="size-4" aria-hidden="true" />
                  </span>
                  <div className="min-w-0">
                <p className="truncate text-xl font-semibold text-slate-950">
                  {formatLabel(accountState.context.subscription.planCode)}
                </p>
                <p className="mt-1 text-sm text-slate-500">Current Compose plan</p>
                  </div>
                </div>
                <Badge
                  variant={
                    accountState.context.subscription.status === "past_due" ? "warning" : "success"
                  }
                >
                  {formatLabel(accountState.context.subscription.status)}
                </Badge>
              </div>
            </div>

            <dl className="mt-5 grid gap-3 text-sm">
              <div className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
                <dt className="flex items-center gap-2 text-slate-500">
                  <UsersRound className="size-4 text-blue-500" aria-hidden="true" />
                  Workspace
                </dt>
                <dd className="truncate font-medium text-slate-950">
                  {accountState.context.organization.name}
                </dd>
              </div>
              <div className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
                <dt className="flex items-center gap-2 text-slate-500">
                  <ShieldCheck className="size-4 text-emerald-500" aria-hidden="true" />
                  Role
                </dt>
                <dd className="font-medium text-slate-950">
                  {formatLabel(accountState.context.membership.role)}
                </dd>
              </div>
              <div className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
                <dt className="text-slate-500">Plan status</dt>
                <dd className="font-medium text-slate-950">
                  {formatLabel(accountState.context.organization.planStatus)}
                </dd>
              </div>
            </dl>
          </div>
        ) : null}
      </div>
    </section>
  );
}
