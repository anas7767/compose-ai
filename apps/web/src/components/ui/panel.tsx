import * as React from "react";

import { cn } from "@/lib/utils";

function Panel({ className, ...props }: React.ComponentProps<"section">) {
  return (
    <section
      className={cn("rounded-lg border border-border bg-card shadow-xs", className)}
      {...props}
    />
  );
}

export { Panel };
