"use client";

import { useAuth, useOrganization, useUser } from "@clerk/nextjs";
import { motion, useReducedMotion } from "motion/react";
import * as React from "react";

import { ActivityPreview } from "@/components/dashboard/activity-preview";
import type { DashboardAccountState } from "@/components/dashboard/dashboard-types";
import { PlanSummary } from "@/components/dashboard/plan-summary";
import { QuickActions } from "@/components/dashboard/quick-actions";
import { RecentProjectsSection } from "@/components/dashboard/recent-projects-section";
import { UsageSummary } from "@/components/dashboard/usage-summary";
import { WelcomeSection } from "@/components/dashboard/welcome-section";
import { AuthApiError, getAuthenticatedContext } from "@/lib/api/auth";

function waitForBootstrap(delay: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }

    const onAbort = () => {
      window.clearTimeout(timeoutId);
      reject(new DOMException("Aborted", "AbortError"));
    };
    const timeoutId = window.setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, delay);

    signal.addEventListener("abort", onAbort, { once: true });
  });
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export function DashboardHome() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const { organization } = useOrganization();
  const { user } = useUser();
  const [accountState, setAccountState] = React.useState<DashboardAccountState>({
    status: "loading",
  });
  const [retryKey, setRetryKey] = React.useState(0);
  const reduceMotion = useReducedMotion();

  React.useEffect(() => {
    if (!isLoaded || !isSignedIn) {
      return;
    }

    const controller = new AbortController();

    async function loadAccountContext() {
      setAccountState({ status: "loading" });

      try {
        const token = await getToken();

        if (!token) {
          throw new Error("Missing Clerk session token.");
        }

        for (let attempt = 0; attempt < 4; attempt += 1) {
          try {
            const context = await getAuthenticatedContext(token, controller.signal);

            if (!controller.signal.aborted) {
              setAccountState({ context, status: "ready" });
            }
            return;
          } catch (error) {
            const bootstrapPending = error instanceof AuthApiError && error.status === 428;

            if (!bootstrapPending || attempt === 3) {
              throw error;
            }

            await waitForBootstrap(300 * (attempt + 1), controller.signal);
          }
        }
      } catch (error) {
        if (!controller.signal.aborted && !isAbortError(error)) {
          setAccountState({ status: "error" });
        }
      }
    }

    void loadAccountContext();

    return () => {
      controller.abort();
    };
  }, [getToken, isLoaded, isSignedIn, retryKey]);

  const accountContext = accountState.status === "ready" ? accountState.context : null;
  const name = user?.firstName ?? user?.fullName?.split(" ")[0] ?? "there";
  const organizationName =
    organization?.name ?? accountContext?.organization.name ?? "Personal workspace";
  const retry = React.useCallback(() => setRetryKey((current) => current + 1), []);
  const sectionTransition = {
    duration: reduceMotion ? 0 : 0.22,
    ease: "easeOut" as const,
  };

  return (
    <div className="compose-dashboard-light -mx-4 -my-6 min-h-[calc(100dvh-4rem)] px-4 py-6 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <motion.div
          animate={{ opacity: 1, y: 0 }}
          initial={{ opacity: 0, y: reduceMotion ? 0 : 8 }}
          transition={sectionTransition}
        >
          <WelcomeSection name={name} organizationName={organizationName} />
        </motion.div>

        <motion.div
          animate={{ opacity: 1, y: 0 }}
          initial={{ opacity: 0, y: reduceMotion ? 0 : 8 }}
          transition={{ ...sectionTransition, delay: reduceMotion ? 0 : 0.04 }}
        >
          <QuickActions />
        </motion.div>

        <div className="grid items-start gap-6 xl:grid-cols-12">
          <motion.div
            animate={{ opacity: 1, y: 0 }}
            className="min-w-0 xl:col-span-8"
            initial={{ opacity: 0, y: reduceMotion ? 0 : 8 }}
            transition={{ ...sectionTransition, delay: reduceMotion ? 0 : 0.08 }}
          >
            <RecentProjectsSection />
          </motion.div>
          <motion.aside
            animate={{ opacity: 1, y: 0 }}
            aria-label="Account overview"
            className="min-w-0 space-y-6 xl:col-span-4"
            initial={{ opacity: 0, y: reduceMotion ? 0 : 8 }}
            transition={{ ...sectionTransition, delay: reduceMotion ? 0 : 0.12 }}
          >
            <UsageSummary accountState={accountState} onRetry={retry} />
            <PlanSummary accountState={accountState} onRetry={retry} />
          </motion.aside>
        </div>

        <motion.div
          animate={{ opacity: 1, y: 0 }}
          initial={{ opacity: 0, y: reduceMotion ? 0 : 8 }}
          transition={{ ...sectionTransition, delay: reduceMotion ? 0 : 0.16 }}
        >
          <ActivityPreview />
        </motion.div>
      </div>
    </div>
  );
}
