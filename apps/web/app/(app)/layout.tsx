import { auth } from "@clerk/nextjs/server";

import { AuthBootstrapper } from "@/components/auth/auth-bootstrapper";
import { AppShell } from "@/components/layout/app-shell";

export default async function ProtectedAppLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  await auth.protect();

  return (
    <AppShell>
      <AuthBootstrapper />
      {children}
    </AppShell>
  );
}
