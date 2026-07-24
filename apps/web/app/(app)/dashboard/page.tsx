import { auth } from "@clerk/nextjs/server";

import { DashboardHome } from "@/components/dashboard/dashboard-home";

export default async function DashboardPage() {
  await auth.protect();

  return <DashboardHome />;
}
