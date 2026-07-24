"use client";

import { useAuth, useOrganization, useUser } from "@clerk/nextjs";
import { useEffect, useRef, useState } from "react";

import { bootstrapAuthenticatedUser } from "@/lib/api/auth";

export function AuthBootstrapper() {
  const { getToken, isLoaded, isSignedIn, orgId, orgRole } = useAuth();
  const { organization } = useOrganization();
  const { user } = useUser();
  const [status, setStatus] = useState<"idle" | "syncing" | "ready" | "failed">("idle");
  const lastBootstrapKey = useRef<string | null>(null);

  useEffect(() => {
    if (!isLoaded || !isSignedIn || !user) {
      return;
    }

    const loadedUser = user;
    const bootstrapKey = `${loadedUser.id}:${orgId ?? "personal"}`;

    if (lastBootstrapKey.current === bootstrapKey) {
      return;
    }

    let cancelled = false;
    lastBootstrapKey.current = bootstrapKey;
    setStatus("syncing");

    async function bootstrap() {
      const token = await getToken();

      if (!token) {
        throw new Error("Missing Clerk session token.");
      }

      await bootstrapAuthenticatedUser(token, {
        email: loadedUser.primaryEmailAddress?.emailAddress ?? null,
        name: loadedUser.fullName ?? loadedUser.username ?? "Compose AI user",
        avatarUrl: loadedUser.imageUrl ?? null,
        activeClerkOrganizationId: orgId ?? null,
        activeOrganizationName: organization?.name ?? null,
        activeOrganizationSlug: organization?.slug ?? null,
        activeOrganizationRole: orgRole ?? null,
      });
    }

    bootstrap()
      .then(() => {
        if (!cancelled) {
          setStatus("ready");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setStatus("failed");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [getToken, isLoaded, isSignedIn, orgId, orgRole, organization, user]);

  if (status !== "failed") {
    return null;
  }

  return (
    <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
      Compose could not finish account initialization. Refresh once; if it persists, check the API
      and Clerk environment variables.
    </div>
  );
}
