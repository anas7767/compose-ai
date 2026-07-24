import type { AuthContextResponse } from "@compose-ai/shared";

export type DashboardAccountState =
  | { status: "loading" }
  | { status: "error" }
  | { context: AuthContextResponse; status: "ready" };
