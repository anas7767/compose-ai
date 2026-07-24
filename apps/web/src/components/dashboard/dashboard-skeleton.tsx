import { Panel } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";

function SummaryRows({ count }: { count: number }) {
  return (
    <div className="mt-6 space-y-5">
      {Array.from({ length: count }, (_, index) => (
        <div className="space-y-2" key={index}>
          <div className="flex items-center justify-between gap-4">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-4 w-16" />
          </div>
          <Skeleton className="h-1.5 w-full rounded-full" />
        </div>
      ))}
    </div>
  );
}

export function DashboardSkeleton() {
  return (
    <div aria-label="Loading dashboard" className="space-y-8" role="status">
      <div className="space-y-3">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-8 w-72 max-w-full" />
        <Skeleton className="h-4 w-80 max-w-full" />
      </div>

      <section>
        <Skeleton className="h-5 w-28" />
        <Skeleton className="mt-2 h-4 w-44" />
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }, (_, index) => (
            <Skeleton className="h-24 w-full" key={index} />
          ))}
        </div>
      </section>

      <div className="grid items-start gap-6 xl:grid-cols-12">
        <Panel className="min-h-[410px] p-5 sm:p-6 xl:col-span-8">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-2">
              <Skeleton className="h-5 w-32" />
              <Skeleton className="h-4 w-52" />
            </div>
            <Skeleton className="h-6 w-16 rounded-full" />
          </div>
          <Skeleton className="mt-6 h-[300px] w-full" />
        </Panel>

        <aside className="space-y-6 xl:col-span-4">
          <Panel className="p-5">
            <Skeleton className="h-5 w-28" />
            <Skeleton className="mt-2 h-4 w-44" />
            <SummaryRows count={4} />
          </Panel>
          <Panel className="p-5">
            <Skeleton className="h-5 w-28" />
            <SummaryRows count={3} />
          </Panel>
        </aside>
      </div>

      <Panel className="p-5 sm:p-6">
        <Skeleton className="h-5 w-20" />
        <Skeleton className="mt-2 h-4 w-40" />
        <Skeleton className="mt-6 h-48 w-full" />
      </Panel>
      <span className="sr-only">Loading dashboard</span>
    </div>
  );
}
