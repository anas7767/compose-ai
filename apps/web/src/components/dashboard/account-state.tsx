import { CircleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

interface AccountSummaryErrorProps {
  onRetry: () => void;
}

export function AccountSummaryError({ onRetry }: AccountSummaryErrorProps) {
  return (
    <div
      className="flex min-h-36 flex-col items-start justify-center rounded-2xl border border-amber-200 bg-amber-50/70 p-4"
      role="alert"
    >
      <CircleAlert aria-hidden="true" className="size-5 text-amber-600" />
      <p className="mt-3 text-sm font-semibold text-slate-950">Account summary unavailable</p>
      <p className="mt-1 text-sm leading-5 text-slate-600">
        Compose could not load the current workspace limits.
      </p>
      <Button className="mt-4" onClick={onRetry} size="sm" variant="outline">
        Retry
      </Button>
    </div>
  );
}

interface AccountSummarySkeletonProps {
  rows?: number;
}

export function AccountSummarySkeleton({ rows = 3 }: AccountSummarySkeletonProps) {
  return (
    <div aria-label="Loading account summary" className="space-y-5" role="status">
      {Array.from({ length: rows }, (_, index) => (
        <div className="space-y-2 rounded-2xl border border-slate-200 bg-white p-3" key={index}>
          <div className="flex items-center justify-between gap-4">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-4 w-16" />
          </div>
          <Skeleton className="h-1.5 w-full rounded-full" />
        </div>
      ))}
      <span className="sr-only">Loading account summary</span>
    </div>
  );
}
