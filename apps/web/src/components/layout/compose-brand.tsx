import { Building2 } from "lucide-react";
import Link from "next/link";

import { cn } from "@/lib/utils";

interface ComposeBrandProps {
  className?: string;
}

export function ComposeBrand({ className }: ComposeBrandProps) {
  return (
    <Link
      aria-label="Compose AI dashboard"
      className={cn(
        "flex min-w-0 items-center gap-3 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-sidebar",
        className,
      )}
      href="/dashboard"
    >
      <span className="flex size-9 shrink-0 items-center justify-center rounded-md border border-primary/35 bg-accent text-primary shadow-xs">
        <Building2 aria-hidden="true" className="size-4" />
      </span>
      <span className="flex min-w-0 items-baseline gap-1.5">
        <span className="truncate text-sm font-semibold text-sidebar-foreground">Compose</span>
        <span className="text-xs font-medium text-primary">AI</span>
      </span>
    </Link>
  );
}
