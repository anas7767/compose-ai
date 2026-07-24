import { PlotProfilePage } from "@/components/plot-intelligence/plot-profile-page";

interface PlotProfileRouteProps {
  params: Promise<{ projectId: string }>;
}

export default async function PlotProfileRoute({ params }: PlotProfileRouteProps) {
  const { projectId } = await params;
  return <PlotProfilePage projectId={projectId} />;
}
