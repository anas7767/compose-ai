import {
  ArrowUpRight,
  FileUp,
  type LucideIcon,
  Plus,
  UsersRound,
  WandSparkles,
} from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { SectionHeader } from "@/components/ui/section-header";
import { cn } from "@/lib/utils";

const projectActions: {
  description: string;
  href: string | null;
  icon: LucideIcon;
  label: string;
}[] = [
  {
    description: "Start a structured building brief",
    href: "/projects/new",
    icon: Plus,
    label: "Create project",
  },
  {
    description: "Planned for a future phase",
    href: null,
    icon: WandSparkles,
    label: "AI floor plan",
  },
  { description: "Planned for a future phase", href: null, icon: FileUp, label: "Import drawing" },
];

const actionClassName =
  "compose-dashboard-action flex min-h-28 min-w-0 items-start gap-3 rounded-[1.35rem] border border-slate-200/80 bg-white/88 p-4 text-left shadow-sm transition duration-200";

export function QuickActions() {
  const reduceMotion = useReducedMotion();

  return (
    <section aria-labelledby="quick-actions-title">
      <SectionHeader
        description="Common workspace actions"
        title="Quick actions"
        titleId="quick-actions-title"
      />
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {projectActions.map((action) => {
          const Icon = action.icon;

          return action.href ? (
            <motion.div
              initial={{ opacity: 0, y: reduceMotion ? 0 : 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: reduceMotion ? 0 : 0.18, ease: "easeOut" }}
              key={action.label}
            >
              <Link
                className={cn(
                  actionClassName,
                  "hover:-translate-y-0.5 hover:border-violet-200 hover:bg-white hover:shadow-[0_18px_45px_rgba(51,65,85,0.10)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-300 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
                )}
                href={action.href}
              >
                <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-violet-50 text-violet-700">
                  <Icon aria-hidden="true" className="size-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold text-slate-950">{action.label}</span>
                  <span className="mt-2 block text-xs leading-5 text-slate-500">
                    {action.description}
                  </span>
                </span>
                <ArrowUpRight aria-hidden="true" className="size-4 shrink-0 text-slate-400" />
              </Link>
            </motion.div>
          ) : (
            <motion.div
              animate={{ opacity: 1, y: 0 }}
              initial={{ opacity: 0, y: reduceMotion ? 0 : 6 }}
              key={action.label}
              transition={{ duration: reduceMotion ? 0 : 0.18, ease: "easeOut" }}
            >
              <button
                aria-label={`${action.label}, unavailable`}
                className={cn(actionClassName, "cursor-not-allowed opacity-68")}
                disabled
                type="button"
              >
                <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-slate-100 text-slate-500">
                  <Icon aria-hidden="true" className="size-4" />
                </span>
                <span className="min-w-0">
                  <span className="block text-sm font-semibold text-slate-700">{action.label}</span>
                  <Badge className="mt-2" variant="outline">
                    Planned
                  </Badge>
                </span>
              </button>
            </motion.div>
          );
        })}

        <Link
          className={cn(
            actionClassName,
            "hover:-translate-y-0.5 hover:border-violet-200 hover:bg-white hover:shadow-[0_18px_45px_rgba(51,65,85,0.10)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-300 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
          )}
          href="/organization"
        >
          <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-blue-50 text-blue-700">
            <UsersRound aria-hidden="true" className="size-4" />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-sm font-semibold text-slate-950">Manage team</span>
            <span className="mt-2 block text-xs leading-5 text-slate-500">
              Organization settings
            </span>
          </span>
          <ArrowUpRight aria-hidden="true" className="size-4 shrink-0 text-slate-400" />
        </Link>
      </div>
    </section>
  );
}
