import { Skeleton } from "@/components/ui/skeleton";

export function ProjectCardSkeleton() {
  return (
    <div className="overflow-hidden rounded-[1.35rem] border border-slate-200 bg-white shadow-sm">
      <Skeleton className="aspect-[16/10] w-full rounded-none" />
      <div className="space-y-4 p-4">
        <div className="space-y-2">
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-3 w-1/3" />
        </div>
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-1.5 w-full rounded-full" />
        <Skeleton className="h-9 w-full" />
      </div>
    </div>
  );
}
