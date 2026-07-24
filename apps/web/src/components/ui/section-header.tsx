import * as React from "react";

import { cn } from "@/lib/utils";

interface SectionHeaderProps extends React.ComponentProps<"div"> {
  action?: React.ReactNode;
  description?: string;
  title: string;
  titleId?: string;
}

function SectionHeader({
  action,
  className,
  description,
  title,
  titleId,
  ...props
}: SectionHeaderProps) {
  return (
    <div
      className={cn("flex min-w-0 items-start justify-between gap-4", className)}
      {...props}
    >
      <div className="min-w-0">
        <h2 className="text-base font-semibold text-foreground" id={titleId}>
          {title}
        </h2>
        {description ? (
          <p className="mt-1 text-sm leading-5 text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

export { SectionHeader };
