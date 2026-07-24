import { ExteriorDesignPage } from "@/components/exterior-design/exterior-design-page";

interface PageProps {
  params: Promise<{ projectId: string }>;
}

export default async function ProjectExteriorDesignRoute({ params }: PageProps) {
  const { projectId } = await params;
  return <ExteriorDesignPage projectId={projectId} />;
}
