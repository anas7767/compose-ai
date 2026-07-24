import * as React from "react";

import { cn } from "@/lib/utils";

interface FormFieldProps extends React.ComponentProps<"div"> {
  children: React.ReactNode;
  description?: string;
  error?: string;
  htmlFor: string;
  label: string;
  required?: boolean;
}

function FormField({
  children,
  className,
  description,
  error,
  htmlFor,
  label,
  required = false,
  ...props
}: FormFieldProps) {
  const descriptionId = description ? `${htmlFor}-description` : undefined;
  const errorId = error ? `${htmlFor}-error` : undefined;

  return (
    <div className={cn("space-y-2", className)} {...props}>
      <label className="text-sm font-medium text-foreground" htmlFor={htmlFor}>
        {label}
        {required ? <span className="ml-1 text-primary">*</span> : null}
      </label>
      {children}
      {description ? (
        <p className="text-xs leading-5 text-muted-foreground" id={descriptionId}>
          {description}
        </p>
      ) : null}
      {error ? (
        <p className="text-xs leading-5 text-destructive" id={errorId} role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export { FormField };
