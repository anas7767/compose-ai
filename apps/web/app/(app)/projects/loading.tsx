import { ProjectCardSkeleton } from "@/components/projects/project-card-skeleton";
import { Skeleton } from "@/components/ui/skeleton";

export default function ProjectsLoading() {
  return (
    <div aria-label="Loading projects" className="space-y-6" role="status">
      <div className="space-y-2">
        <Skeleton className="h-7 w-32" />
        <Skeleton className="h-4 w-72 max-w-full" />
      </div>
      <Skeleton className="h-12 w-full" />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 6 }, (_, index) => (
          <ProjectCardSkeleton key={index} />
        ))}
      </div>
      <span className="sr-only">Loading projects</span>
    </div>
  );
}
