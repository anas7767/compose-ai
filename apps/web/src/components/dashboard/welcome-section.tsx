import { Building2, CalendarDays, Sparkles } from "lucide-react";

interface WelcomeSectionProps {
  name: string;
  organizationName: string;
}

export function WelcomeSection({ name, organizationName }: WelcomeSectionProps) {
  const today = new Intl.DateTimeFormat("en", {
    day: "numeric",
    month: "long",
    weekday: "long",
  }).format(new Date());

  return (
    <section
      aria-labelledby="dashboard-title"
      className="relative overflow-hidden rounded-[2rem] border border-white/80 bg-white/84 p-5 shadow-[0_24px_80px_rgba(51,65,85,0.10)] backdrop-blur-xl sm:p-7"
    >
      <div aria-hidden="true" className="compose-dashboard-grid" />
      <div aria-hidden="true" className="compose-dashboard-illustration">
        <span />
        <span />
        <span />
      </div>
      <div className="relative z-10 flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-3xl">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex min-w-0 items-center gap-2 rounded-full border border-violet-200/80 bg-white/80 px-3 py-1 text-xs font-medium text-violet-700 shadow-sm">
              <Building2 aria-hidden="true" className="size-3.5 shrink-0" />
              <span className="truncate">{organizationName}</span>
            </span>
            <span className="inline-flex items-center gap-2 rounded-full border border-blue-200/80 bg-white/80 px-3 py-1 text-xs font-medium text-blue-700 shadow-sm">
              <CalendarDays aria-hidden="true" className="size-3.5" />
              {today}
            </span>
          </div>
          <h1
            className="mt-4 text-balance text-3xl font-semibold leading-tight tracking-normal text-slate-950 sm:text-4xl"
            id="dashboard-title"
          >
            Welcome back, {name}
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600 sm:text-base">
            A calm command center for active projects, workspace limits, and design activity.
          </p>
        </div>
        <div className="rounded-2xl border border-slate-200/75 bg-white/82 p-4 shadow-sm lg:w-72">
          <div className="flex items-start gap-3">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-violet-50 text-violet-700">
              <Sparkles aria-hidden="true" className="size-4" />
            </span>
            <div>
              <p className="text-sm font-semibold text-slate-950">Workspace snapshot</p>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                Recent projects, plan allocation, and activity update automatically from Compose.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
