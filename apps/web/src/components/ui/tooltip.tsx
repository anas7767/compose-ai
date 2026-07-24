import * as React from "react";

import { cn } from "@/lib/utils";

interface TooltipProps {
  children: React.ReactNode;
  className?: string;
  content: string;
}

function Tooltip({ children, className, content }: TooltipProps) {
  return (
    <span className={cn("group/tooltip relative inline-flex", className)}>
      {children}
      <span
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-full z-50 mt-2 -translate-x-1/2 whitespace-nowrap rounded-sm border border-border bg-popover px-2 py-1 text-xs text-popover-foreground opacity-0 shadow-sm transition-opacity duration-150 group-focus-within/tooltip:opacity-100 group-hover/tooltip:opacity-100"
        role="tooltip"
      >
        {content}
      </span>
    </span>
  );
}

export { Tooltip };
