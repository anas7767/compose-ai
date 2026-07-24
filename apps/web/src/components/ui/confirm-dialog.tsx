"use client";

import * as React from "react";

import { Button } from "@/components/ui/button";

interface ConfirmDialogProps {
  confirmLabel: string;
  description: string;
  destructive?: boolean;
  onConfirm: () => void;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  pending?: boolean;
  title: string;
}

export function ConfirmDialog({
  confirmLabel,
  description,
  destructive = false,
  onConfirm,
  onOpenChange,
  open,
  pending = false,
  title,
}: ConfirmDialogProps) {
  const dialogRef = React.useRef<HTMLDialogElement>(null);
  const titleId = React.useId();
  const descriptionId = React.useId();

  React.useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      aria-describedby={descriptionId}
      aria-labelledby={titleId}
      className="fixed inset-0 z-50 m-auto w-[min(28rem,calc(100vw-2rem))] rounded-lg border border-border bg-popover p-0 text-popover-foreground shadow-lg backdrop:bg-black/75"
      onCancel={(event) => {
        event.preventDefault();
        if (!pending) onOpenChange(false);
      }}
      onClose={() => {
        if (open && !pending) onOpenChange(false);
      }}
      ref={dialogRef}
    >
      <div className="p-6">
        <h2 className="text-base font-semibold" id={titleId}>
          {title}
        </h2>
        <p className="mt-2 text-sm leading-6 text-muted-foreground" id={descriptionId}>
          {description}
        </p>
        <div className="mt-6 flex justify-end gap-3">
          <Button disabled={pending} onClick={() => onOpenChange(false)} variant="ghost">
            Cancel
          </Button>
          <Button
            disabled={pending}
            onClick={onConfirm}
            variant={destructive ? "destructive" : "default"}
          >
            {pending ? "Working..." : confirmLabel}
          </Button>
        </div>
      </div>
    </dialog>
  );
}
