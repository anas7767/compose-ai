"use client";

import * as React from "react";

export type AutosaveStatus = "idle" | "saving" | "saved" | "error";

interface SerializedAutosaveOptions<TSnapshot, TResult> {
  onConfirmed: (snapshot: TSnapshot, result: TResult) => void;
  save: (snapshot: TSnapshot) => Promise<TResult>;
}

export function useSerializedAutosave<TSnapshot, TResult>({
  onConfirmed,
  save,
}: SerializedAutosaveOptions<TSnapshot, TResult>) {
  const [status, setStatus] = React.useState<AutosaveStatus>("idle");
  const pendingRef = React.useRef<TSnapshot | null>(null);
  const drainPromiseRef = React.useRef<Promise<void> | null>(null);
  const saveRef = React.useRef(save);
  const confirmedRef = React.useRef(onConfirmed);

  React.useEffect(() => {
    saveRef.current = save;
    confirmedRef.current = onConfirmed;
  }, [onConfirmed, save]);

  const startDrain = React.useCallback((): Promise<void> => {
    if (drainPromiseRef.current) return drainPromiseRef.current;

    const drain = async () => {
      while (pendingRef.current) {
        const snapshot = pendingRef.current;
        pendingRef.current = null;
        setStatus("saving");
        try {
          const result = await saveRef.current(snapshot);
          confirmedRef.current(snapshot, result);
          setStatus(pendingRef.current ? "saving" : "saved");
        } catch (error) {
          if (!pendingRef.current) pendingRef.current = snapshot;
          setStatus("error");
          throw error;
        }
      }
    };

    const activeDrain = drain().finally(() => {
      drainPromiseRef.current = null;
    });
    drainPromiseRef.current = activeDrain;
    return activeDrain;
  }, []);

  const queue = React.useCallback(
    (snapshot: TSnapshot) => {
      pendingRef.current = snapshot;
      void startDrain().catch(() => undefined);
    },
    [startDrain],
  );

  const flush = React.useCallback(
    async (snapshot: TSnapshot) => {
      pendingRef.current = snapshot;
      await startDrain();
    },
    [startDrain],
  );

  const retry = React.useCallback(() => {
    if (pendingRef.current) void startDrain().catch(() => undefined);
  }, [startDrain]);

  return { flush, queue, retry, status };
}
