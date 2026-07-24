"use client";

import { ArrowRight, FolderKanban, Plus } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import Link from "next/link";

import { ProjectCard } from "@/components/projects/project-card";
import { ProjectCardSkeleton } from "@/components/projects/project-card-skeleton";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { SectionHeader } from "@/components/ui/section-header";
import { useProjectList } from "@/hooks/use-projects";

export function RecentProjectsSection() {
  const projects = useProjectList("active", "", null, 6);
  const reduceMotion = useReducedMotion();

  return (
    <section
      aria-labelledby="recent-projects-title"
      className="rounded-[1.75rem] border border-white/80 bg-white/90 p-5 shadow-[0_24px_80px_rgba(51,65,85,0.09)] backdrop-blur-xl sm:p-6"
    >
      <SectionHeader
        action={
          <Button asChild size="sm" variant="ghost">
            <Link href="/projects">
              View all
              <ArrowRight aria-hidden="true" />
            </Link>
          </Button>
        }
        description="Recently opened building projects"
        title="Recent projects"
        titleId="recent-projects-title"
      />

      <div
        className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3"
        data-slot="project-grid"
      >
        {projects.isLoading
          ? Array.from({ length: 3 }, (_, index) => <ProjectCardSkeleton key={index} />)
          : null}
        {projects.isError ? (
          <EmptyState
            action={<Button onClick={() => projects.refetch()}>Retry</Button>}
            className="col-span-full min-h-[300px] border-t border-border px-4"
            description="Compose could not load recent projects."
            icon={FolderKanban}
            title="Recent projects unavailable"
          />
        ) : null}
        {projects.data?.projects.length === 0 ? (
          <EmptyState
            action={
              <Button asChild>
                <Link href="/projects/new">
                  <Plus aria-hidden="true" />
                  Create project
                </Link>
              </Button>
            }
            className="col-span-full min-h-[300px] border-t border-border px-4"
            description="Create a structured building brief to start your workspace."
            icon={FolderKanban}
            title="No active projects"
          />
        ) : null}
        {projects.data?.projects.map((project, index) => (
          <motion.div
            animate={{ opacity: 1, y: 0 }}
            initial={{ opacity: 0, y: reduceMotion ? 0 : 8 }}
            key={project.id}
            transition={{
              delay: reduceMotion ? 0 : index * 0.035,
              duration: reduceMotion ? 0 : 0.18,
              ease: "easeOut",
            }}
          >
            <ProjectCard project={project} view="active" />
          </motion.div>
        ))}
      </div>
    </section>
  );
}
