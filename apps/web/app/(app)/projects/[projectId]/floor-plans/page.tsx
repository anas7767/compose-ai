import { FloorPlanGeneratorPage } from "@/components/floor-plans/floor-plan-generator-page";

interface FloorPlanPageProps {
  params: Promise<{ projectId: string }>;
}

export default async function FloorPlanPage({ params }: FloorPlanPageProps) {
  const { projectId } = await params;
  return <FloorPlanGeneratorPage projectId={projectId} />;
}
