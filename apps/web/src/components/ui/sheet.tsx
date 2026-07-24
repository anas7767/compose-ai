"use client";

import { X } from "lucide-react";
import * as React from "react";

import { IconButton } from "@/components/ui/icon-button";
import { cn } from "@/lib/utils";

interface SheetProps {
  children: React.ReactNode;
  className?: string;
  description: string;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  title: string;
}

function Sheet({ children, className, description, onOpenChange, open, title }: SheetProps) {
  const dialogRef = React.useRef<HTMLDialogElement>(null);
  const titleId = React.useId();
  const descriptionId = React.useId();

  React.useEffect(() => {
    const dialog = dialogRef.current;

    if (!dialog) {
      return;
    }

    if (open && !dialog.open) {
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  React.useEffect(() => {
    if (!open) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  return (
    <dialog
      aria-describedby={descriptionId}
      aria-labelledby={titleId}
      className="fixed inset-0 z-50 m-0 h-dvh max-h-none w-screen max-w-none items-stretch justify-start overflow-hidden bg-transparent p-0 text-foreground backdrop:bg-black/75 open:flex"
      onCancel={(event) => {
        event.preventDefault();
        onOpenChange(false);
      }}
      onClick={(event) => {
        if (event.currentTarget === event.target) {
          onOpenChange(false);
        }
      }}
      onClose={() => {
        if (open) {
          onOpenChange(false);
        }
      }}
      ref={dialogRef}
    >
      <div
        className={cn(
          "flex h-dvh w-[min(20rem,88vw)] flex-col border-r border-sidebar-border bg-sidebar shadow-lg",
          className,
        )}
      >
        <div className="flex h-16 shrink-0 items-center justify-between border-b border-sidebar-border px-4">
          <div className="min-w-0">
            <h2 className="truncate text-sm font-semibold" id={titleId}>
              {title}
            </h2>
            <p className="sr-only" id={descriptionId}>
              {description}
            </p>
          </div>
          <IconButton autoFocus label="Close navigation" onClick={() => onOpenChange(false)}>
            <X aria-hidden="true" />
          </IconButton>
        </div>
        {children}
      </div>
    </dialog>
  );
}

export { Sheet };
