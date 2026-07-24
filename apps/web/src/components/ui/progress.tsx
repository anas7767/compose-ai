import * as React from "react";

import { cn } from "@/lib/utils";

interface ProgressProps extends Omit<React.ComponentProps<"div">, "children"> {
  label: string;
  max?: number;
  value: number;
}

function Progress({ className, label, max = 100, value, ...props }: ProgressProps) {
  const safeMax = Math.max(max, 1);
  const safeValue = Math.min(Math.max(value, 0), safeMax);
  const percentage = (safeValue / safeMax) * 100;

  return (
    <div
      aria-label={label}
      aria-valuemax={safeMax}
      aria-valuemin={0}
      aria-valuenow={safeValue}
      className={cn("h-1.5 w-full overflow-hidden rounded-full bg-secondary", className)}
      role="progressbar"
      {...props}
    >
      <div
        className="h-full rounded-full bg-primary transition-[width] duration-150"
        style={{ width: `${percentage}%` }}
      />
    </div>
  );
}

export { Progress };
