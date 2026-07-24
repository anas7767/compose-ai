import { Building2 } from "lucide-react";
import Link from "next/link";

import { cn } from "@/lib/utils";

interface PublicBrandProps {
  className?: string;
}

export function PublicBrand({ className }: PublicBrandProps) {
  return (
    <Link
      aria-label="Compose AI home"
      className={cn(
        "group inline-flex items-center gap-3 rounded-md text-slate-950 outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-4",
        className,
      )}
      href="/"
    >
      <span className="flex size-9 items-center justify-center rounded-md border border-violet-200/80 bg-white/80 text-violet-700 shadow-[0_6px_20px_rgb(80_70_180_/_0.12)] backdrop-blur-xl transition-transform duration-300 group-hover:-translate-y-0.5">
        <Building2 aria-hidden="true" className="size-[17px]" strokeWidth={1.8} />
      </span>
      <span className="flex items-baseline gap-1.5">
        <span className="text-[15px] font-semibold text-slate-950">Compose</span>
        <span className="text-xs font-semibold text-violet-600">AI</span>
      </span>
    </Link>
  );
}

