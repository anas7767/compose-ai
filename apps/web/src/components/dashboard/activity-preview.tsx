"use client";

import { Activity, ArrowRight } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { SectionHeader } from "@/components/ui/section-header";
import { Skeleton } from "@/components/ui/skeleton";
import { useProjectActivity } from "@/hooks/use-projects";

function formatAction(action: string): string {
  return action
    .replace("project.", "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function ActivityPreview() {
  const activity = useProjectActivity(6);
  const reduceMotion = useReducedMotion();

  return (
    <section
      aria-labelledby="activity-preview-title"
      className="rounded-[1.75rem] border border-white/80 bg-white/90 p-5 shadow-[0_24px_80px_rgba(51,65,85,0.09)] backdrop-blur-xl sm:p-6"
    >
      <SectionHeader
        description="Latest workspace events"
        title="Activity"
        titleId="activity-preview-title"
      />
      {activity.isLoading ? (
        <div className="mt-5 grid gap-3">
          {Array.from({ length: 4 }, (_, index) => (
            <div className="flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-4" key={index}>
              <Skeleton className="size-10 shrink-0 rounded-2xl" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-44" />
                <Skeleton className="h-3 w-28" />
              </div>
            </div>
          ))}
        </div>
      ) : null}
      {activity.isError ? (
        <EmptyState
          action={<Button onClick={() => activity.refetch()}>Retry</Button>}
          className="mt-5 min-h-48 rounded-2xl border border-dashed border-slate-200 bg-slate-50/60"
          description="Compose could not load workspace activity."
          icon={Activity}
          title="Activity unavailable"
        />
      ) : null}
      {activity.data?.length ? (
        <ol className="mt-5 grid gap-3">
          {activity.data.map((event, index) => (
            <motion.li
              animate={{ opacity: 1, y: 0 }}
              className="flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition duration-200 hover:border-violet-200 hover:shadow-[0_14px_36px_rgba(51,65,85,0.08)]"
              initial={{ opacity: 0, y: reduceMotion ? 0 : 6 }}
              key={event.id}
              transition={{
                delay: reduceMotion ? 0 : index * 0.025,
                duration: reduceMotion ? 0 : 0.18,
                ease: "easeOut",
              }}
            >
              <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-violet-50 text-violet-700">
                <Activity aria-hidden="true" className="size-4" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-slate-950">
                  {formatAction(event.action)}: {event.projectName}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {event.actorName ?? "Compose user"} · {new Date(event.createdAt).toLocaleString()}
                </p>
              </div>
              <Button asChild size="sm" variant="ghost">
                <Link
                  aria-label={`Open ${event.projectName}`}
                  href={`/projects/${event.projectId}`}
                >
                  <ArrowRight aria-hidden="true" />
                </Link>
              </Button>
            </motion.li>
          ))}
        </ol>
      ) : null}
      {!activity.isLoading && !activity.isError && !activity.data?.length ? (
        <EmptyState
          className="mt-5 min-h-48 rounded-2xl border border-dashed border-slate-200 bg-slate-50/60"
          description="Project lifecycle events will appear here."
          icon={Activity}
          title="No recent activity"
        />
      ) : null}
    </section>
  );
}
