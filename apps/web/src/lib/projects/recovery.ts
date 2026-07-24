import { z } from "zod";

const recoverySchema = z.object({
  expiresAt: z.number(),
  organizationId: z.string(),
  projectId: z.string().nullable(),
  revision: z.number().int().nonnegative(),
  savedAt: z.number(),
  schemaVersion: z.literal(1),
  snapshot: z.record(z.string(), z.unknown()),
  userId: z.string(),
});

export type ProjectRecoveryRecord = z.infer<typeof recoverySchema>;

const RECOVERY_PREFIX = "compose-ai:project-wizard:v1";
const RECOVERY_TTL_MS = 7 * 24 * 60 * 60 * 1000;

interface RecoveryScope {
  organizationId: string;
  projectId: string | null;
  userId: string;
}

function recoveryKey(scope: RecoveryScope): string {
  return `${RECOVERY_PREFIX}:${scope.userId}:${scope.organizationId}:${scope.projectId ?? "new"}`;
}

export function writeProjectRecovery(
  scope: RecoveryScope,
  revision: number,
  snapshot: Record<string, unknown>,
): void {
  if (typeof window === "undefined") return;
  const now = Date.now();
  const record: ProjectRecoveryRecord = {
    expiresAt: now + RECOVERY_TTL_MS,
    organizationId: scope.organizationId,
    projectId: scope.projectId,
    revision,
    savedAt: now,
    schemaVersion: 1,
    snapshot,
    userId: scope.userId,
  };
  try {
    window.localStorage.setItem(recoveryKey(scope), JSON.stringify(record));
  } catch {
    // Browser privacy or quota policies may disable recovery storage.
  }
}

export function readProjectRecovery(scope: RecoveryScope): ProjectRecoveryRecord | null {
  if (typeof window === "undefined") return null;
  let value: string | null = null;
  try {
    value = window.localStorage.getItem(recoveryKey(scope));
  } catch {
    return null;
  }
  if (!value) return null;
  try {
    const record = recoverySchema.parse(JSON.parse(value));
    if (record.expiresAt <= Date.now()) {
      window.localStorage.removeItem(recoveryKey(scope));
      return null;
    }
    return record;
  } catch {
    window.localStorage.removeItem(recoveryKey(scope));
    return null;
  }
}

export function clearProjectRecovery(scope: RecoveryScope): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(recoveryKey(scope));
  } catch {
    // Recovery storage is best-effort when browser storage is unavailable.
  }
}

export function clearProjectRecoveryRevision(scope: RecoveryScope, revision: number): void {
  const record = readProjectRecovery(scope);
  if (record?.revision === revision) clearProjectRecovery(scope);
}
