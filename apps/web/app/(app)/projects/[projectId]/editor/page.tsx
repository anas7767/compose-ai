import { FloorPlanEditorPage } from "@/components/floor-plan-editor/floor-plan-editor-page";

interface EditorPageProps {
  params: Promise<{ projectId: string }>;
}

export default async function EditorPage({ params }: EditorPageProps) {
  const { projectId } = await params;
  return <FloorPlanEditorPage projectId={projectId} />;
}
