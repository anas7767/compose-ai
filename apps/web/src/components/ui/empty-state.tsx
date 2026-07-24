import type { LucideIcon } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

interface EmptyStateProps extends React.ComponentProps<"div"> {
  action?: React.ReactNode;
  description: string;
  icon: LucideIcon;
  title: string;
}

function EmptyState({
  action,
  className,
  description,
  icon: Icon,
  title,
  ...props
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex min-h-56 flex-col items-center justify-center px-6 py-10 text-center",
        className,
      )}
      {...props}
    >
      <div className="flex size-12 items-center justify-center rounded-md border border-primary/25 bg-accent text-primary">
        <Icon className="size-5" aria-hidden="true" />
      </div>
      <h3 className="mt-4 text-sm font-semibold text-foreground">{title}</h3>
      <p className="mt-2 max-w-sm text-sm leading-6 text-muted-foreground">{description}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

export { EmptyState };
