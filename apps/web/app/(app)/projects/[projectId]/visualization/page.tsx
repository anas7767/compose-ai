import { BuildingVisualizationPage } from "@/components/building-visualization/building-visualization-page";

interface PageProps {
  params: Promise<{ projectId: string }>;
}

export default async function ProjectVisualizationRoute({ params }: PageProps) {
  const { projectId } = await params;
  return <BuildingVisualizationPage projectId={projectId} />;
}
