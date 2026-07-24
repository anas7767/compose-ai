import { Suspense } from "react";

import { ProjectListPage } from "@/components/projects/project-list-page";

import ProjectsLoading from "./loading";

export default function ProjectsPage() {
  return (
    <Suspense fallback={<ProjectsLoading />}>
      <ProjectListPage />
    </Suspense>
  );
}
