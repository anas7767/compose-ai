"use client";

import { useAuth } from "@clerk/nextjs";
import type { ProjectListView, ProjectSummary } from "@compose-ai/shared";
import { useQueryClient } from "@tanstack/react-query";
import { FolderKanban, Plus, Search } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import * as React from "react";

import { ProjectCard } from "@/components/projects/project-card";
import { ProjectCardSkeleton } from "@/components/projects/project-card-skeleton";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { useInfiniteProjectList } from "@/hooks/use-projects";
import {
  archiveProject,
  deleteProject,
  duplicateProject,
  restoreDeletedProject,
  restoreProject,
} from "@/lib/api/projects";
import { cn } from "@/lib/utils";

const views: { label: string; value: ProjectListView }[] = [
  { label: "Active", value: "active" },
  { label: "Drafts", value: "drafts" },
  { label: "Archived", value: "archived" },
  { label: "Trash", value: "trash" },
];

export function ProjectListPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { getToken } = useAuth();
  const rawView = searchParams.get("view");
  const view = views.some((item) => item.value === rawView)
    ? (rawView as ProjectListView)
    : "active";
  const [search, setSearch] = React.useState("");
  const deferredSearch = React.useDeferredValue(search);
  const projects = useInfiniteProjectList(view, deferredSearch);
  const projectItems = React.useMemo(
    () => projects.data?.pages.flatMap((page) => page.projects) ?? [],
    [projects.data],
  );
  const [busyId, setBusyId] = React.useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = React.useState<ProjectSummary | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const refresh = React.useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ["projects"] });
  }, [queryClient]);

  const runAction = React.useCallback(
    async (
      project: ProjectSummary,
      action: "archive" | "restore" | "duplicate" | "restoreDeleted",
    ) => {
      setBusyId(project.id);
      setError(null);
      try {
        const token = await getToken();
        if (!token) throw new Error("Missing Clerk session token.");
        if (action === "archive") await archiveProject(token, project.id, project.version);
        if (action === "restore") await restoreProject(token, project.id, project.version);
        if (action === "duplicate") {
          const duplicate = await duplicateProject(token, project.id, {}, crypto.randomUUID());
          router.push(`/projects/${duplicate.id}/edit`);
        }
        if (action === "restoreDeleted") {
          await restoreDeletedProject(token, project.id, project.version);
        }
        await refresh();
      } catch (actionError) {
        setError(actionError instanceof Error ? actionError.message : "Project action failed.");
      } finally {
        setBusyId(null);
      }
    },
    [getToken, refresh, router],
  );

  const confirmDelete = React.useCallback(async () => {
    if (!deleteTarget) return;
    setBusyId(deleteTarget.id);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Missing Clerk session token.");
      await deleteProject(token, deleteTarget.id, deleteTarget.version);
      setDeleteTarget(null);
      await refresh();
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Project deletion failed.");
    } finally {
      setBusyId(null);
    }
  }, [deleteTarget, getToken, refresh]);

  const emptyCopy = {
    active: ["No active projects", "Complete a draft to make it active."],
    drafts: ["No project drafts", "Create a project to begin a structured brief."],
    archived: ["No archived projects", "Archived projects remain recoverable here."],
    trash: ["Trash is empty", "Soft-deleted projects can be restored from this view."],
  }[view];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Projects</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Manage building briefs and site requirements.
          </p>
        </div>
        <Button asChild>
          <Link href="/projects/new">
            <Plus aria-hidden="true" />
            Create project
          </Link>
        </Button>
      </div>

      <div className="flex flex-col gap-3 border-b border-border pb-4 lg:flex-row lg:items-center lg:justify-between">
        <nav aria-label="Project views" className="flex gap-1 overflow-x-auto">
          {views.map((item) => (
            <Link
              aria-current={view === item.value ? "page" : undefined}
              className={cn(
                "h-9 shrink-0 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-secondary hover:text-foreground",
                view === item.value && "bg-accent text-foreground",
              )}
              href={item.value === "active" ? "/projects" : `/projects?view=${item.value}`}
              key={item.value}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="relative w-full lg:w-72">
          <Search
            aria-hidden="true"
            className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            aria-label="Search projects by name"
            className="pl-9"
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search projects"
            value={search}
          />
        </div>
      </div>

      {error ? (
        <div
          className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
          role="alert"
        >
          {error}
        </div>
      ) : null}

      {projects.isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }, (_, index) => (
            <ProjectCardSkeleton key={index} />
          ))}
        </div>
      ) : null}

      {projects.isError ? (
        <EmptyState
          action={<Button onClick={() => projects.refetch()}>Retry</Button>}
          description="Compose could not load this project view."
          icon={FolderKanban}
          title="Projects unavailable"
        />
      ) : null}

      {projects.data && projectItems.length === 0 ? (
        <EmptyState
          action={
            view === "drafts" || view === "active" ? (
              <Button asChild>
                <Link href="/projects/new">Create project</Link>
              </Button>
            ) : undefined
          }
          description={emptyCopy[1]}
          icon={FolderKanban}
          title={emptyCopy[0]}
        />
      ) : null}

      {projectItems.length ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {projectItems.map((project) => (
            <ProjectCard
              busy={busyId === project.id}
              key={project.id}
              onArchive={(item) => void runAction(item, "archive")}
              onDelete={setDeleteTarget}
              onDuplicate={(item) => void runAction(item, "duplicate")}
              onRestore={(item) => void runAction(item, "restore")}
              onRestoreDeleted={(item) => void runAction(item, "restoreDeleted")}
              project={project}
              view={view}
            />
          ))}
        </div>
      ) : null}

      {projects.hasNextPage ? (
        <div className="flex justify-center border-t border-border pt-5">
          <Button
            disabled={projects.isFetchingNextPage}
            onClick={() => void projects.fetchNextPage()}
            variant="outline"
          >
            {projects.isFetchingNextPage ? "Loading projects..." : "Load more"}
          </Button>
        </div>
      ) : null}

      <ConfirmDialog
        confirmLabel="Move to trash"
        description={
          deleteTarget
            ? `${deleteTarget.name} will be soft deleted and can be restored from Trash.`
            : "The project will be moved to Trash."
        }
        destructive
        onConfirm={() => void confirmDelete()}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        open={deleteTarget !== null}
        pending={busyId === deleteTarget?.id}
        title="Delete project?"
      />
    </div>
  );
}
