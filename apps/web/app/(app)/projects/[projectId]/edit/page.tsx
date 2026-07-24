import { ProjectWizard } from "@/components/projects/project-wizard";

interface EditProjectPageProps {
  params: Promise<{ projectId: string }>;
}

export default async function EditProjectPage({ params }: EditProjectPageProps) {
  const { projectId } = await params;
  return <ProjectWizard projectId={projectId} />;
}
