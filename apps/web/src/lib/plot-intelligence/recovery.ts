import type { PlotFormValues } from "@/lib/plot-intelligence/form";

interface PlotRecoveryRecord {
  expiresAt: number;
  projectId: string;
  savedAt: number;
  schemaVersion: 1;
  userId: string;
  values: PlotFormValues;
}

const RECOVERY_PREFIX = "compose-ai:plot-profile:v1";
const RECOVERY_TTL_MS = 7 * 24 * 60 * 60 * 1000;

function recoveryKey(userId: string, projectId: string): string {
  return `${RECOVERY_PREFIX}:${userId}:${projectId}`;
}

export function readPlotRecovery(userId: string, projectId: string): PlotRecoveryRecord | null {
  if (typeof window === "undefined") return null;
  try {
    const value = window.localStorage.getItem(recoveryKey(userId, projectId));
    if (!value) return null;
    const record = JSON.parse(value) as PlotRecoveryRecord;
    if (record.schemaVersion !== 1 || record.expiresAt <= Date.now()) {
      window.localStorage.removeItem(recoveryKey(userId, projectId));
      return null;
    }
    return record;
  } catch {
    return null;
  }
}

export function writePlotRecovery(userId: string, projectId: string, values: PlotFormValues): void {
  if (typeof window === "undefined") return;
  const now = Date.now();
  const record: PlotRecoveryRecord = {
    expiresAt: now + RECOVERY_TTL_MS,
    projectId,
    savedAt: now,
    schemaVersion: 1,
    userId,
    values,
  };
  try {
    window.localStorage.setItem(recoveryKey(userId, projectId), JSON.stringify(record));
  } catch {
    // Local recovery is best effort when browser storage is unavailable.
  }
}

export function clearPlotRecovery(userId: string, projectId: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(recoveryKey(userId, projectId));
  } catch {
    // Local recovery is best effort when browser storage is unavailable.
  }
}
