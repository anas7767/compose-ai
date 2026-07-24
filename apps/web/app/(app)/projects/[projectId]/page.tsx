import { ProjectDetailPage } from "@/components/projects/project-detail-page";

interface ProjectPageProps {
  params: Promise<{ projectId: string }>;
}

export default async function ProjectPage({ params }: ProjectPageProps) {
  const { projectId } = await params;
  return <ProjectDetailPage projectId={projectId} />;
}
