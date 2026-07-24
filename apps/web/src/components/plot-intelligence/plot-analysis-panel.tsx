import type { PlotAnalysis, UnitSystem } from "@compose-ai/shared";
import {
  AlertTriangle,
  Compass,
  ParkingCircle,
  Ruler,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Panel } from "@/components/ui/panel";
import { Progress } from "@/components/ui/progress";
import { SectionHeader } from "@/components/ui/section-header";

interface PlotAnalysisPanelProps {
  analysis: PlotAnalysis;
  unitSystem: UnitSystem;
}

function titleCase(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatArea(value: number | null, unitSystem: UnitSystem): string {
  if (value === null) return "Awaiting geometry";
  const unit = unitSystem === "imperial" ? "ft2" : "m2";
  return `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(value)} ${unit}`;
}

export function PlotAnalysisPanel({ analysis, unitSystem }: PlotAnalysisPanelProps) {
  const healthVariant = analysis.plotHealthStatus === "invalid" ? "warning" : "success";

  return (
    <aside className="space-y-5">
      <Panel className="p-5">
        <SectionHeader description="Data quality, not regulatory approval" title="Plot health" />
        <div className="mt-5 flex items-end justify-between gap-4">
          <div>
            <p className="text-3xl font-semibold tabular-nums text-foreground">
              {analysis.plotHealthScore}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">Health score</p>
          </div>
          <Badge variant={healthVariant}>{titleCase(analysis.plotHealthStatus)}</Badge>
        </div>
        <div className="mt-4 space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Completeness</span>
            <span className="font-medium tabular-nums">{analysis.plotCompleteness}%</span>
          </div>
          <Progress label="Plot completeness" value={analysis.plotCompleteness} />
        </div>
      </Panel>

      <Panel className="p-5">
        <SectionHeader description="Preliminary, non-regulatory outputs" title="Site intelligence" />
        <dl className="mt-4 divide-y divide-border border-y border-border">
          <Metric icon={Ruler} label="Pre-regulation area" value={formatArea(analysis.preRegulationBuildableArea, unitSystem)} />
          <Metric icon={ParkingCircle} label="Parking" value={titleCase(analysis.parkingStatus)} />
          <Metric icon={Compass} label="Feasibility" value={titleCase(analysis.feasibilityStatus)} />
          <Metric icon={ShieldCheck} label="Regulations" value="Not configured" />
        </dl>
      </Panel>

      <Panel className="p-5">
        <SectionHeader description="Resolve errors before relying on the result" title="Validation" />
        {analysis.issues.length ? (
          <ul className="mt-4 divide-y divide-border border-y border-border">
            {analysis.issues.map((issue) => (
              <li className="flex gap-3 py-3 text-sm" key={`${issue.code}-${issue.field}`}>
                <AlertTriangle
                  aria-hidden="true"
                  className={
                    issue.severity === "error"
                      ? "mt-0.5 size-4 shrink-0 text-destructive"
                      : "mt-0.5 size-4 shrink-0 text-primary"
                  }
                />
                <div>
                  <p className="font-medium text-foreground">{issue.message}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{titleCase(issue.severity)}</p>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-4 text-sm text-muted-foreground">No validation issues.</p>
        )}
      </Panel>
    </aside>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-3 text-sm">
      <span className="flex min-w-0 items-center gap-2 text-muted-foreground">
        <Icon aria-hidden="true" className="size-4 shrink-0" />
        {label}
      </span>
      <span className="max-w-[58%] truncate text-right font-medium text-foreground">{value}</span>
    </div>
  );
}
