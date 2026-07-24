"use client";

import { useAuth } from "@clerk/nextjs";
import type { ProjectDetail } from "@compose-ai/shared";
import { useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  ArchiveRestore,
  ArrowLeft,
  Building2,
  Copy,
  Cuboid,
  DraftingCompass,
  ImageIcon,
  MapPin,
  MapPinned,
  Pencil,
  Sparkles,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Panel } from "@/components/ui/panel";
import { SectionHeader } from "@/components/ui/section-header";
import { Skeleton } from "@/components/ui/skeleton";
import { useProjectActivity, useProjectDetail } from "@/hooks/use-projects";
import {
  archiveProject,
  deleteProject,
  duplicateProject,
  restoreProject,
} from "@/lib/api/projects";

interface ProjectDetailPageProps {
  projectId: string;
}

function formatLabel(value: string | null): string {
  if (!value) return "Not specified";
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  const displayValue =
    value === null || value === undefined || value === "" ? "Not specified" : value;
  return (
    <div className="grid gap-1 py-3 text-sm sm:grid-cols-[160px_minmax(0,1fr)]">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 font-medium text-foreground">{displayValue}</dd>
    </div>
  );
}

export function ProjectDetailPage({ projectId }: ProjectDetailPageProps) {
  const project = useProjectDetail(projectId);
  const activity = useProjectActivity(20, projectId);
  const { getToken } = useAuth();
  const queryClient = useQueryClient();
  const router = useRouter();
  const [busy, setBusy] = React.useState(false);
  const [confirmDelete, setConfirmDelete] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const refresh = React.useCallback(
    async (updated?: ProjectDetail) => {
      if (updated) queryClient.setQueryData(["projects", "detail", projectId], updated);
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
    [projectId, queryClient],
  );

  const runLifecycleAction = React.useCallback(
    async (action: "archive" | "restore" | "duplicate" | "delete") => {
      if (!project.data) return;
      setBusy(true);
      setError(null);
      try {
        const token = await getToken();
        if (!token) throw new Error("Missing Clerk session token.");
        if (action === "archive") {
          await refresh(await archiveProject(token, projectId, project.data.version));
        }
        if (action === "restore") {
          await refresh(await restoreProject(token, projectId, project.data.version));
        }
        if (action === "duplicate") {
          const duplicated = await duplicateProject(token, projectId, {}, crypto.randomUUID());
          await refresh();
          router.push(`/projects/${duplicated.id}/edit`);
        }
        if (action === "delete") {
          await deleteProject(token, projectId, project.data.version);
          await refresh();
          router.push("/projects?view=trash");
        }
      } catch (actionError) {
        setError(actionError instanceof Error ? actionError.message : "Project action failed.");
      } finally {
        setBusy(false);
        setConfirmDelete(false);
      }
    },
    [getToken, project.data, projectId, refresh, router],
  );

  if (project.isLoading) return <ProjectDetailSkeleton />;
  if (project.isError || !project.data) {
    return (
      <EmptyState
        action={<Button onClick={() => project.refetch()}>Retry</Button>}
        description="The project may have been removed or is unavailable in this workspace."
        icon={Building2}
        title="Project unavailable"
      />
    );
  }

  const data = project.data;
  const siteLabel = [data.site.city, data.site.region, data.country].filter(Boolean).join(", ");

  return (
    <div className="space-y-6">
      <Button asChild size="sm" variant="ghost">
        <Link href="/projects">
          <ArrowLeft aria-hidden="true" />
          Projects
        </Link>
      </Button>

      <div className="flex flex-col gap-5 border-b border-border pb-6 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <span className="rounded-full border border-border bg-secondary px-2 py-1 text-xs">
              {formatLabel(data.status)}
            </span>
            <span>{formatLabel(data.projectType)}</span>
          </div>
          <h1 className="mt-3 truncate text-2xl font-semibold text-foreground">{data.name}</h1>
          <p className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
            <MapPin aria-hidden="true" className="size-4" />
            {siteLabel || "Site not specified"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button asChild>
            <Link href={`/projects/${data.id}/floor-plans`}>
              <DraftingCompass aria-hidden="true" />
              Floor plans
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link href={`/projects/${data.id}/editor`}>
              <DraftingCompass aria-hidden="true" />
              2D editor
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link href={`/projects/${data.id}/visualization`}>
              <Cuboid aria-hidden="true" />
              3D view
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link href={`/projects/${data.id}/exterior`}>
              <ImageIcon aria-hidden="true" />
              Exterior
            </Link>
          </Button>
          <Button asChild>
            <Link href={`/projects/${data.id}/architect`}>
              <Sparkles aria-hidden="true" />
              AI Architect
            </Link>
          </Button>
          {data.status !== "archived" ? (
            <Button asChild variant="outline">
              <Link href={`/projects/${data.id}/edit`}>
                <Pencil aria-hidden="true" />
                Edit project
              </Link>
            </Button>
          ) : null}
          <Button asChild variant="outline">
            <Link href={`/projects/${data.id}/plot`}>
              <MapPinned aria-hidden="true" />
              Plot profile
            </Link>
          </Button>
          {data.status === "archived" ? (
            <Button disabled={busy} onClick={() => void runLifecycleAction("restore")}>
              <ArchiveRestore aria-hidden="true" />
              Restore
            </Button>
          ) : (
            <Button
              disabled={busy}
              onClick={() => void runLifecycleAction("archive")}
              variant="outline"
            >
              <Archive aria-hidden="true" />
              Archive
            </Button>
          )}
          <Button
            disabled={busy}
            onClick={() => void runLifecycleAction("duplicate")}
            variant="outline"
          >
            <Copy aria-hidden="true" />
            Duplicate
          </Button>
          <Button disabled={busy} onClick={() => setConfirmDelete(true)} variant="ghost">
            <Trash2 aria-hidden="true" />
            Delete
          </Button>
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

      <div className="grid gap-6 xl:grid-cols-12">
        <div className="space-y-6 xl:col-span-8">
          <Panel className="p-5 sm:p-6">
            <SectionHeader description="Core project information" title="Overview" />
            <dl className="mt-4 divide-y divide-border border-y border-border">
              <DetailRow label="Description" value={data.description} />
              <DetailRow label="Units" value={formatLabel(data.unitSystem)} />
              <DetailRow label="Currency" value={data.currency} />
              <DetailRow label="Country" value={data.country} />
              <DetailRow label="Tags" value={data.tags.length ? data.tags.join(", ") : null} />
              <DetailRow label="Completeness" value={`${data.profileCompleteness}%`} />
            </dl>
          </Panel>

          <Panel className="p-5 sm:p-6">
            <SectionHeader description="Plot, access, and location" title="Site profile" />
            <dl className="mt-4 divide-y divide-border border-y border-border">
              <DetailRow
                label="Address"
                value={[
                  data.site.addressLine1,
                  data.site.addressLine2,
                  data.site.city,
                  data.site.region,
                  data.site.postalCode,
                ]
                  .filter(Boolean)
                  .join(", ")}
              />
              <DetailRow label="Plot shape" value={formatLabel(data.site.plotShape)} />
              <DetailRow
                label="Dimensions"
                value={
                  data.site.plotLength && data.site.plotWidth
                    ? `${data.site.plotLength} x ${data.site.plotWidth}`
                    : null
                }
              />
              <DetailRow label="Plot area" value={data.site.plotArea} />
              <DetailRow label="Primary road" value={formatLabel(data.site.roadDirectionPrimary)} />
              <DetailRow
                label="Secondary road"
                value={formatLabel(data.site.roadDirectionSecondary)}
              />
              <DetailRow label="Open sides" value={data.site.openSides} />
              <DetailRow label="Corner plot" value={data.site.cornerPlot ? "Yes" : "No"} />
              <DetailRow label="Boundary" value={formatLabel(data.site.boundaryStatus)} />
            </dl>
          </Panel>

          <Panel className="p-5 sm:p-6">
            <SectionHeader
              action={
                <Button asChild size="sm" variant="ghost">
                  <Link href={`/projects/${data.id}/plot`}>Open plot profile</Link>
                </Button>
              }
              description="Validated geometry and preliminary feasibility"
              title="Plot intelligence"
            />
            <dl className="mt-4 divide-y divide-border border-y border-border">
              <DetailRow label="Plot completeness" value={`${data.plotSummary.completeness}%`} />
              <DetailRow label="Plot health" value={formatLabel(data.plotSummary.healthStatus)} />
              <DetailRow
                label="Feasibility"
                value={formatLabel(data.plotSummary.feasibilityStatus)}
              />
              <DetailRow
                label="Pre-regulation area"
                value={data.plotSummary.preRegulationBuildableArea}
              />
              <DetailRow label="Parking" value={formatLabel(data.plotSummary.parkingStatus)} />
              <DetailRow
                label="Validation"
                value={`${data.plotSummary.validationErrorCount} errors, ${data.plotSummary.validationWarningCount} warnings`}
              />
            </dl>
          </Panel>

          <Panel className="p-5 sm:p-6">
            <SectionHeader description="Space and construction brief" title="Requirements" />
            <dl className="mt-4 divide-y divide-border border-y border-border">
              <DetailRow label="Bedrooms" value={data.requirements.bedrooms} />
              <DetailRow label="Bathrooms" value={data.requirements.bathrooms} />
              <DetailRow label="Floors" value={data.requirements.floors} />
              <DetailRow label="Parking" value={data.requirements.parkingSpaces} />
              <DetailRow
                label="Budget"
                value={
                  data.requirements.budget === null
                    ? null
                    : `${data.currency} ${data.requirements.budget.toLocaleString()}`
                }
              />
              <DetailRow
                label="Quality"
                value={formatLabel(data.requirements.constructionQuality)}
              />
              <DetailRow label="Style" value={data.requirements.preferredStyle} />
              <DetailRow label="Vastu" value={formatLabel(data.requirements.vastuPreference)} />
              <DetailRow label="Notes" value={data.requirements.notes} />
            </dl>

            <div className="mt-6">
              <h3 className="text-sm font-semibold">Custom rooms</h3>
              {data.roomRequirements.length ? (
                <div className="mt-3 divide-y divide-border border-y border-border">
                  {data.roomRequirements.map((room) => (
                    <div
                      className="flex items-center justify-between gap-4 py-3 text-sm"
                      key={room.id}
                    >
                      <div>
                        <p className="font-medium">{room.name}</p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {room.roomType ?? "Custom space"}
                        </p>
                      </div>
                      <span className="shrink-0 tabular-nums text-muted-foreground">
                        Quantity: {room.quantity}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-3 text-sm text-muted-foreground">No custom room requirements.</p>
              )}
            </div>
          </Panel>
        </div>

        <aside className="space-y-6 xl:col-span-4">
          <Panel className="p-5">
            <SectionHeader title="Client" />
            <dl className="mt-4 divide-y divide-border border-y border-border">
              <DetailRow label="Name" value={data.client.name} />
              <DetailRow label="Company" value={data.client.company} />
              <DetailRow label="Email" value={data.client.email} />
              <DetailRow label="Phone" value={data.client.phone} />
              <DetailRow label="Address" value={data.client.address} />
            </dl>
          </Panel>

          <Panel className="p-5">
            <SectionHeader description="Project lifecycle events" title="Activity" />
            {activity.isLoading ? (
              <div className="mt-4 space-y-3">
                {Array.from({ length: 4 }, (_, index) => (
                  <Skeleton className="h-12 w-full" key={index} />
                ))}
              </div>
            ) : null}
            {activity.data?.length ? (
              <ol className="mt-4 divide-y divide-border border-y border-border">
                {activity.data.map((event) => (
                  <li className="py-3 text-sm" key={event.id}>
                    <p className="font-medium">
                      {formatLabel(event.action.replace("project.", ""))}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {event.actorName ?? "Compose user"} |{" "}
                      {new Date(event.createdAt).toLocaleString()}
                    </p>
                  </li>
                ))}
              </ol>
            ) : null}
            {!activity.isLoading && !activity.data?.length ? (
              <p className="mt-4 text-sm text-muted-foreground">No project activity recorded.</p>
            ) : null}
          </Panel>
        </aside>
      </div>

      <ConfirmDialog
        confirmLabel="Move to trash"
        description={`${data.name} will be soft deleted and can be restored from Trash.`}
        destructive
        onConfirm={() => void runLifecycleAction("delete")}
        onOpenChange={setConfirmDelete}
        open={confirmDelete}
        pending={busy}
        title="Delete project?"
      />
    </div>
  );
}

function ProjectDetailSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-9 w-24" />
      <Skeleton className="h-28 w-full" />
      <div className="grid gap-6 xl:grid-cols-12">
        <div className="space-y-6 xl:col-span-8">
          <Skeleton className="h-72 w-full" />
          <Skeleton className="h-96 w-full" />
        </div>
        <Skeleton className="h-80 w-full xl:col-span-4" />
      </div>
    </div>
  );
}
