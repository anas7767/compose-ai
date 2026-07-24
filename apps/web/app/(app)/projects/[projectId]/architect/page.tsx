import { AIArchitectPage } from "@/components/ai-architect/ai-architect-page";

interface AIArchitectRouteProps {
  params: Promise<{ projectId: string }>;
}

export default async function AIArchitectRoute({ params }: AIArchitectRouteProps) {
  const { projectId } = await params;
  return <AIArchitectPage projectId={projectId} />;
}
