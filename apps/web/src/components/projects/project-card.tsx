"use client";

import type { ProjectListView, ProjectSummary } from "@compose-ai/shared";
import {
  Archive,
  ArchiveRestore,
  Building2,
  Copy,
  Eye,
  MapPinned,
  MapPin,
  Pencil,
  RotateCcw,
  Trash2,
} from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";

interface ProjectCardProps {
  busy?: boolean;
  onArchive?: (project: ProjectSummary) => void;
  onDelete?: (project: ProjectSummary) => void;
  onDuplicate?: (project: ProjectSummary) => void;
  onRestore?: (project: ProjectSummary) => void;
  onRestoreDeleted?: (project: ProjectSummary) => void;
  project: ProjectSummary;
  view: ProjectListView;
}

function formatLabel(value: string | null): string {
  if (!value) return "Type not set";
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

export function ProjectCard({
  busy = false,
  onArchive,
  onDelete,
  onDuplicate,
  onRestore,
  onRestoreDeleted,
  project,
  view,
}: ProjectCardProps) {
  const updatedAt = new Intl.DateTimeFormat("en", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(project.updatedAt));
  const profileCompleteness = Math.min(Math.max(project.profileCompleteness, 0), 100);
  const plotCompleteness = Math.min(Math.max(project.plotSummary.completeness, 0), 100);

  return (
    <article className="compose-dashboard-project-card group overflow-hidden rounded-[1.35rem] border border-slate-200/85 bg-white shadow-sm transition duration-200 hover:-translate-y-0.5 hover:border-violet-200 hover:shadow-[0_20px_55px_rgba(51,65,85,0.11)]">
      {view === "trash" ? (
        <div className="compose-dashboard-project-thumb relative flex aspect-[16/10] items-center justify-center border-b border-slate-200/80">
          <Building2 aria-hidden="true" className="size-9 text-violet-500/75" />
          <span className="absolute left-3 top-3">
            <Badge variant="neutral">Deleted</Badge>
          </span>
          <span className="absolute bottom-3 right-3 rounded-full border border-slate-200 bg-white/92 px-2.5 py-1 text-xs tabular-nums text-slate-600 shadow-sm">
            {profileCompleteness}% complete
          </span>
        </div>
      ) : (
        <Link
          aria-label={`Open ${project.name}`}
          className="compose-dashboard-project-thumb relative flex aspect-[16/10] items-center justify-center border-b border-slate-200/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-violet-300"
          href={`/projects/${project.id}`}
        >
          <div className="compose-dashboard-project-lines" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
          <Building2 aria-hidden="true" className="relative z-10 size-9 text-violet-500/75" />
          <span className="absolute left-3 top-3">
            <Badge variant={project.status === "active" ? "success" : "neutral"}>
              {formatLabel(project.status)}
            </Badge>
          </span>
          <span className="absolute bottom-3 right-3 rounded-full border border-slate-200 bg-white/92 px-2.5 py-1 text-xs tabular-nums text-slate-600 shadow-sm">
            {profileCompleteness}% complete
          </span>
        </Link>
      )}

      <div className="p-4">
        <div className="min-w-0">
          {view === "trash" ? (
            <p className="truncate text-sm font-semibold text-slate-950">{project.name}</p>
          ) : (
            <Link
              className="block truncate text-sm font-semibold text-slate-950 hover:text-violet-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-300"
              href={`/projects/${project.id}`}
            >
              {project.name}
            </Link>
          )}
          <p className="mt-1 text-xs text-slate-500">{formatLabel(project.projectType)}</p>
        </div>

        <div className="mt-4 flex items-center justify-between gap-3 text-xs text-slate-500">
          <span className="flex min-w-0 items-center gap-1.5">
            <MapPin aria-hidden="true" className="size-3.5 shrink-0" />
            <span className="truncate">{project.city ?? project.country ?? "Site not set"}</span>
          </span>
          <span className="shrink-0">{updatedAt}</span>
        </div>

        <div className="mt-3 border-t border-slate-200 pt-3 text-xs">
          <div className="flex items-center justify-between gap-3">
          <span className="flex min-w-0 items-center gap-1.5 text-slate-500">
            <MapPinned aria-hidden="true" className="size-3.5 shrink-0" />
            Plot {formatLabel(project.plotSummary.healthStatus)}
          </span>
          <span className="shrink-0 tabular-nums text-slate-500">
            {plotCompleteness}% ready
          </span>
          </div>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-gradient-to-r from-violet-500 to-blue-500"
              style={{ width: `${plotCompleteness}%` }}
            />
          </div>
        </div>

        {project.tags.length ? (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {project.tags.slice(0, 3).map((tag) => (
              <Badge key={tag} variant="outline">
                {tag}
              </Badge>
            ))}
          </div>
        ) : null}

        <div className="mt-4 flex items-center justify-between border-t border-slate-200 pt-3">
          {view === "trash" ? (
            <Button
              disabled={busy || !onRestoreDeleted}
              onClick={() => onRestoreDeleted?.(project)}
              size="sm"
              variant="outline"
            >
              <RotateCcw aria-hidden="true" />
              Restore
            </Button>
          ) : project.status === "archived" ? (
            <Button asChild size="sm" variant="ghost">
              <Link href={`/projects/${project.id}`}>
                <Eye aria-hidden="true" />
                Open
              </Link>
            </Button>
          ) : (
            <Button asChild size="sm" variant="ghost">
              <Link href={`/projects/${project.id}/edit`}>
                <Pencil aria-hidden="true" />
                {project.status === "draft" ? "Resume" : "Edit"}
              </Link>
            </Button>
          )}

          {view !== "trash" && (onArchive || onDelete || onDuplicate || onRestore) ? (
            <div className="flex items-center gap-1">
              {project.status === "archived" && onRestore ? (
                <IconButton
                  disabled={busy}
                  label={`Restore ${project.name}`}
                  onClick={() => onRestore(project)}
                  size="sm"
                  variant="ghost"
                >
                  <ArchiveRestore aria-hidden="true" />
                </IconButton>
              ) : onArchive ? (
                <IconButton
                  disabled={busy}
                  label={`Archive ${project.name}`}
                  onClick={() => onArchive(project)}
                  size="sm"
                  variant="ghost"
                >
                  <Archive aria-hidden="true" />
                </IconButton>
              ) : null}
              {onDuplicate ? (
                <IconButton
                  disabled={busy}
                  label={`Duplicate ${project.name}`}
                  onClick={() => onDuplicate(project)}
                  size="sm"
                  variant="ghost"
                >
                  <Copy aria-hidden="true" />
                </IconButton>
              ) : null}
              {onDelete ? (
                <IconButton
                  disabled={busy}
                  label={`Delete ${project.name}`}
                  onClick={() => onDelete(project)}
                  size="sm"
                  variant="ghost"
                >
                  <Trash2 aria-hidden="true" />
                </IconButton>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </article>
  );
}
