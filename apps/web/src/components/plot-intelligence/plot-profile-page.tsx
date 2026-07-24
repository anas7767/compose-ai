"use client";

import { useAuth } from "@clerk/nextjs";
import type { PlotAnalysis, PlotBoundaryVersion, PlotIntelligence } from "@compose-ai/shared";
import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Check,
  FileJson,
  History,
  LoaderCircle,
  MapPinned,
  Plus,
  RefreshCw,
  RotateCcw,
  Save,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import Link from "next/link";
import * as React from "react";
import { useFieldArray, useForm } from "react-hook-form";

import { BoundaryPreview } from "@/components/plot-intelligence/boundary-preview";
import { PlotAnalysisPanel } from "@/components/plot-intelligence/plot-analysis-panel";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/ui/panel";
import { SectionHeader } from "@/components/ui/section-header";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { usePlotBoundaryHistory, usePlotIntelligence } from "@/hooks/use-plot-intelligence";
import {
  clearPlotBoundary,
  recalculatePlotAnalysis,
  restorePlotBoundary,
  undoPlotBoundaryRestore,
  updatePlotProfile,
  validatePlotProfile,
} from "@/lib/api/plot-intelligence";
import {
  convertFormValues,
  emptyPlotFormValues,
  extractPolygon,
  plotFormToRequest,
  plotShapes,
  plotToFormValues,
  roadDirections,
  type PlotFormError,
  type PlotFormValues,
  validatePlotForm,
} from "@/lib/plot-intelligence/form";
import {
  clearPlotRecovery,
  readPlotRecovery,
  writePlotRecovery,
} from "@/lib/plot-intelligence/recovery";

interface PlotProfilePageProps {
  projectId: string;
}

function formatLabel(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function emptyRoad(index: number) {
  return {
    boundaryEdgeIndex: "",
    label: index === 0 ? "Primary frontage" : `Road side ${index + 1}`,
    direction: roadDirections[index] ?? "north",
    isPrimary: index === 0,
    roadName: "",
    roadWidth: "",
    accessAllowed: true,
    sortOrder: index,
  };
}

export function PlotProfilePage({ projectId }: PlotProfilePageProps) {
  const { getToken, isLoaded, userId } = useAuth();
  const queryClient = useQueryClient();
  const plotQuery = usePlotIntelligence(projectId);
  const historyQuery = usePlotBoundaryHistory(projectId);
  const form = useForm<PlotFormValues>({ defaultValues: emptyPlotFormValues() });
  const roads = useFieldArray({ control: form.control, name: "roadSides" });
  const vertices = useFieldArray({ control: form.control, name: "vertices" });
  const [initialized, setInitialized] = React.useState(false);
  const [recovered, setRecovered] = React.useState(false);
  const [hasUnsaved, setHasUnsaved] = React.useState(false);
  const [boundaryDirty, setBoundaryDirty] = React.useState(false);
  const [validationAnalysis, setValidationAnalysis] = React.useState<PlotAnalysis | null>(null);
  const [validationErrors, setValidationErrors] = React.useState<PlotFormError[]>([]);
  const [actionError, setActionError] = React.useState<string | null>(null);
  const [saving, setSaving] = React.useState(false);
  const [validating, setValidating] = React.useState(false);
  const [restoring, setRestoring] = React.useState<PlotBoundaryVersion | null>(null);
  const [clearingBoundary, setClearingBoundary] = React.useState(false);
  const [undoing, setUndoing] = React.useState(false);
  const [now, setNow] = React.useState(() => Date.now());
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const initializedRef = React.useRef(false);

  const watchedVertices = form.watch("vertices");
  const watchedCoordinateSpace = form.watch("coordinateSpace");
  const watchedUnitSystem = form.watch("unitSystem");
  const watchedRoadSides = form.watch("roadSides");
  const activeAnalysis = validationAnalysis ?? plotQuery.data?.analysis;

  const hydrate = React.useCallback(
    (plot: PlotIntelligence, recovery?: PlotFormValues | null) => {
      form.reset(recovery ?? plotToFormValues(plot));
      setBoundaryDirty(Boolean(recovery));
      setValidationAnalysis(null);
      setValidationErrors([]);
      setHasUnsaved(Boolean(recovery));
      setInitialized(true);
      initializedRef.current = true;
    },
    [form],
  );

  React.useEffect(() => {
    if (!plotQuery.data || !isLoaded || initializedRef.current) return;
    const recovery = userId ? readPlotRecovery(userId, projectId) : null;
    hydrate(plotQuery.data, recovery?.values);
    setRecovered(Boolean(recovery));
  }, [hydrate, isLoaded, plotQuery.data, projectId, userId]);

  React.useEffect(() => {
    if (!initialized || !userId) return;
    const subscription = form.watch((values) => {
      setHasUnsaved(true);
      writePlotRecovery(userId, projectId, values as PlotFormValues);
    });
    return () => subscription.unsubscribe();
  }, [form, initialized, projectId, userId]);

  React.useEffect(() => {
    if (!initialized || !userId || !boundaryDirty) return;
    writePlotRecovery(userId, projectId, form.getValues());
  }, [boundaryDirty, form, initialized, projectId, userId]);

  React.useEffect(() => {
    if (!hasUnsaved) return;
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    const onDocumentClick = (event: MouseEvent) => {
      if (
        event.defaultPrevented ||
        event.button !== 0 ||
        event.altKey ||
        event.ctrlKey ||
        event.metaKey ||
        event.shiftKey
      ) {
        return;
      }
      const link = event.target instanceof Element ? event.target.closest("a[href]") : null;
      if (!(link instanceof HTMLAnchorElement) || link.target === "_blank" || link.download) return;
      const destination = new URL(link.href, window.location.href);
      const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
      const next = `${destination.pathname}${destination.search}${destination.hash}`;
      if (destination.origin !== window.location.origin || current === next) return;
      if (!window.confirm("Leave this plot profile? Unsaved changes remain recoverable locally.")) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    document.addEventListener("click", onDocumentClick, true);
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload);
      document.removeEventListener("click", onDocumentClick, true);
    };
  }, [hasUnsaved]);

  React.useEffect(() => {
    if (!plotQuery.data?.activeUndo) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [plotQuery.data?.activeUndo]);

  const applyServerPlot = React.useCallback(
    async (plot: PlotIntelligence) => {
      queryClient.setQueryData(["plots", "detail", projectId], plot);
      await queryClient.invalidateQueries({ queryKey: ["plots", "boundaries", projectId] });
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      hydrate(plot);
      if (userId) clearPlotRecovery(userId, projectId);
      setRecovered(false);
    },
    [hydrate, projectId, queryClient, userId],
  );

  const clientValidate = React.useCallback(() => {
    const errors = validatePlotForm(form.getValues(), boundaryDirty);
    setValidationErrors(errors);
    return errors.length === 0;
  }, [boundaryDirty, form]);

  const requestForCurrentForm = React.useCallback(() => {
    return plotFormToRequest(form.getValues(), boundaryDirty);
  }, [boundaryDirty, form]);

  const save = React.useCallback(async () => {
    if (!plotQuery.data || !clientValidate()) return;
    setSaving(true);
    setActionError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Missing Clerk session token.");
      const plot = await updatePlotProfile(
        token,
        projectId,
        plotQuery.data.projectVersion,
        requestForCurrentForm(),
        crypto.randomUUID(),
      );
      await applyServerPlot(plot);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Plot profile could not be saved.");
    } finally {
      setSaving(false);
    }
  }, [applyServerPlot, clientValidate, getToken, plotQuery.data, projectId, requestForCurrentForm]);

  const validate = React.useCallback(async () => {
    if (!clientValidate()) return;
    setValidating(true);
    setActionError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Missing Clerk session token.");
      setValidationAnalysis(await validatePlotProfile(token, projectId, requestForCurrentForm()));
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Plot validation failed.");
    } finally {
      setValidating(false);
    }
  }, [clientValidate, getToken, projectId, requestForCurrentForm]);

  const handleUnitChange = React.useCallback(
    (nextUnitSystem: PlotFormValues["unitSystem"]) => {
      const next = convertFormValues(form.getValues(), nextUnitSystem);
      if (next.coordinateSpace === "local_cartesian") {
        next.boundarySource = "manual_vertices";
      }
      form.reset(next);
      setBoundaryDirty((current) => current || next.coordinateSpace === "local_cartesian");
      setHasUnsaved(true);
    },
    [form],
  );

  const applyGeoJsonText = React.useCallback((text?: string) => {
    try {
      const geoJsonText = text ?? form.getValues("geoJsonText");
      const polygon = extractPolygon(JSON.parse(geoJsonText));
      vertices.replace(
        polygon.coordinates[0].slice(0, -1).map(([x, y]) => ({ x: String(x), y: String(y) })),
      );
      form.setValue("boundarySource", "geojson_import");
      setBoundaryDirty(true);
      setActionError(null);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "GeoJSON could not be read.");
    }
  }, [form, vertices]);

  const readGeoJsonFile = React.useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) return;
      try {
        const text = await file.text();
        form.setValue("geoJsonText", text, { shouldDirty: true });
        applyGeoJsonText(text);
      } catch (error) {
        setActionError(error instanceof Error ? error.message : "GeoJSON file could not be read.");
      } finally {
        event.target.value = "";
      }
    },
    [applyGeoJsonText, form],
  );

  const restoreBoundary = React.useCallback(async () => {
    if (!restoring || !plotQuery.data) return;
    setActionError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Missing Clerk session token.");
      const restored = await restorePlotBoundary(
        token,
        projectId,
        restoring.id,
        plotQuery.data.projectVersion,
        crypto.randomUUID(),
      );
      await applyServerPlot(restored.plot);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Boundary could not be restored.");
    } finally {
      setRestoring(null);
    }
  }, [applyServerPlot, getToken, plotQuery.data, projectId, restoring]);

  const clearBoundary = React.useCallback(async () => {
    if (!plotQuery.data) return;
    setActionError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Missing Clerk session token.");
      await applyServerPlot(
        await clearPlotBoundary(token, projectId, plotQuery.data.projectVersion, crypto.randomUUID()),
      );
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Boundary could not be cleared.");
    } finally {
      setClearingBoundary(false);
    }
  }, [applyServerPlot, getToken, plotQuery.data, projectId]);

  const undoRestore = React.useCallback(async () => {
    const undo = plotQuery.data?.activeUndo;
    if (!undo || !plotQuery.data) return;
    setUndoing(true);
    setActionError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Missing Clerk session token.");
      await applyServerPlot(
        await undoPlotBoundaryRestore(
          token,
          projectId,
          undo.id,
          plotQuery.data.projectVersion,
          crypto.randomUUID(),
        ),
      );
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Boundary restore could not be undone.");
    } finally {
      setUndoing(false);
    }
  }, [applyServerPlot, getToken, plotQuery.data, projectId]);

  const recalculate = React.useCallback(async () => {
    if (!plotQuery.data) return;
    setActionError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Missing Clerk session token.");
      await applyServerPlot(
        await recalculatePlotAnalysis(
          token,
          projectId,
          plotQuery.data.projectVersion,
          crypto.randomUUID(),
        ),
      );
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Analysis could not be recalculated.");
    }
  }, [applyServerPlot, getToken, plotQuery.data, projectId]);

  if (plotQuery.isLoading || !initialized) return <PlotProfileSkeleton />;
  if (plotQuery.isError || !plotQuery.data) {
    return (
      <EmptyState
        action={<Button onClick={() => plotQuery.refetch()}>Retry</Button>}
        description="Compose could not load this plot profile."
        icon={MapPinned}
        title="Plot profile unavailable"
      />
    );
  }

  const plot = plotQuery.data;
  const canEdit = plot.canEdit;
  const undoRemaining = plot.activeUndo
    ? Math.max(0, new Date(plot.activeUndo.expiresAt).getTime() - now)
    : 0;

  return (
    <form className="space-y-6" onSubmit={(event) => { event.preventDefault(); void save(); }}>
      <div className="flex flex-col gap-4 border-b border-border pb-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <Button asChild className="-ml-3" size="sm" variant="ghost">
            <Link href={`/projects/${projectId}`}>
              <ArrowLeft aria-hidden="true" />
              Project
            </Link>
          </Button>
          <h1 className="mt-3 text-2xl font-semibold text-foreground">Plot profile</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Validate site geometry and preliminary feasibility before design work begins.
          </p>
        </div>
        {canEdit ? (
          <div className="flex flex-wrap gap-2">
            <Button disabled={validating || saving} onClick={() => void validate()} type="button" variant="outline">
              {validating ? <LoaderCircle aria-hidden="true" className="animate-spin" /> : <Check aria-hidden="true" />}
              Validate plot
            </Button>
            <Button disabled={saving} type="submit">
              {saving ? <LoaderCircle aria-hidden="true" className="animate-spin" /> : <Save aria-hidden="true" />}
              {saving ? "Saving..." : "Save plot"}
            </Button>
          </div>
        ) : null}
      </div>

      {recovered ? (
        <div className="rounded-md border border-primary/30 bg-accent px-4 py-3 text-sm text-accent-foreground" role="status">
          Recovered unsaved plot changes from this browser.
        </div>
      ) : null}
      {plot.activeUndo && undoRemaining > 0 ? (
        <div className="flex flex-col gap-3 rounded-md border border-primary/30 bg-accent px-4 py-3 sm:flex-row sm:items-center sm:justify-between" role="status">
          <p className="text-sm text-accent-foreground">
            Boundary restored. Undo is available for {Math.ceil(undoRemaining / 1000)} seconds.
          </p>
          <Button disabled={undoing || !canEdit} onClick={() => void undoRestore()} size="sm" type="button" variant="outline">
            <RotateCcw aria-hidden="true" />
            {undoing ? "Undoing..." : "Undo restore"}
          </Button>
        </div>
      ) : null}
      {actionError ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive" role="alert">
          {actionError}
        </div>
      ) : null}
      {validationErrors.length ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive" role="alert">
          <p className="font-medium">Resolve the following before saving:</p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {validationErrors.map((error) => <li key={`${error.field}-${error.message}`}>{error.message}</li>)}
          </ul>
        </div>
      ) : null}

      <div className="grid items-start gap-6 xl:grid-cols-12">
        <div className="space-y-6 xl:col-span-8">
          <Panel className="p-5 sm:p-6">
            <SectionHeader description="Values are displayed in the selected project unit." title="Plot profile" />
            <div className="mt-5 grid gap-5 sm:grid-cols-2">
              <FormField htmlFor="unitSystem" label="Unit system">
                <Select disabled={!canEdit} id="unitSystem" onChange={(event) => handleUnitChange(event.target.value as PlotFormValues["unitSystem"])} value={watchedUnitSystem}>
                  <option value="metric">Metric</option>
                  <option value="imperial">Imperial</option>
                </Select>
              </FormField>
              <FormField htmlFor="plotShape" label="Plot shape">
                <Select disabled={!canEdit} id="plotShape" {...form.register("plotShape")}>
                  <option value="">Select plot shape</option>
                  {plotShapes.map((shape) => <option key={shape} value={shape}>{formatLabel(shape)}</option>)}
                </Select>
              </FormField>
              <FormField htmlFor="plotLength" label="Plot length">
                <Input disabled={!canEdit} id="plotLength" inputMode="decimal" {...form.register("plotLength")} />
              </FormField>
              <FormField htmlFor="plotWidth" label="Plot width">
                <Input disabled={!canEdit} id="plotWidth" inputMode="decimal" {...form.register("plotWidth")} />
              </FormField>
              <FormField htmlFor="plotArea" label="Declared plot area">
                <Input disabled={!canEdit} id="plotArea" inputMode="decimal" {...form.register("plotArea")} />
              </FormField>
              <FormField htmlFor="openSides" label="Open sides">
                <Input disabled={!canEdit} id="openSides" inputMode="numeric" {...form.register("openSides")} />
              </FormField>
            </div>
            <label className="mt-5 flex min-h-11 items-center gap-3 rounded-md border border-border bg-secondary/30 px-3 text-sm">
              <input disabled={!canEdit} className="size-4 accent-primary" type="checkbox" {...form.register("cornerPlot")} />
              Corner plot
            </label>
          </Panel>

          <Panel className="p-5 sm:p-6">
            <SectionHeader description="Align plot information to a stable north reference." title="Orientation" />
            <div className="mt-5 grid gap-5 sm:grid-cols-3">
              <FormField htmlFor="orientationDegrees" label="Primary frontage bearing">
                <Input disabled={!canEdit} id="orientationDegrees" inputMode="decimal" placeholder="0 to 359.999" {...form.register("orientationDegrees")} />
              </FormField>
              <FormField htmlFor="northReference" label="North reference">
                <Select disabled={!canEdit} id="northReference" {...form.register("northReference")}>
                  <option value="">Select reference</option>
                  <option value="true">True north</option>
                  <option value="magnetic">Magnetic north</option>
                  <option value="assumed">Assumed north</option>
                </Select>
              </FormField>
              <FormField htmlFor="northRotationDegrees" label="North rotation">
                <Input disabled={!canEdit} id="northRotationDegrees" inputMode="decimal" placeholder="0 to 359.999" {...form.register("northRotationDegrees")} />
              </FormField>
            </div>
          </Panel>

          <Panel className="p-5 sm:p-6">
            <SectionHeader
              action={canEdit ? <Button onClick={() => roads.append(emptyRoad(roads.fields.length))} size="sm" type="button" variant="outline"><Plus aria-hidden="true" />Add road side</Button> : undefined}
              description="Road access is preliminary site context, not regulation guidance."
              title="Road sides"
            />
            <div className="mt-5 space-y-4">
              {roads.fields.map((road, index) => (
                <div className="grid gap-4 border border-border bg-secondary/20 p-4 sm:grid-cols-2" key={road.id}>
                  <FormField htmlFor={`road-${index}-label`} label="Label">
                    <Input disabled={!canEdit} id={`road-${index}-label`} {...form.register(`roadSides.${index}.label`)} />
                  </FormField>
                  <FormField htmlFor={`road-${index}-direction`} label="Direction">
                    <Select disabled={!canEdit} id={`road-${index}-direction`} {...form.register(`roadSides.${index}.direction`)}>
                      {roadDirections.map((direction) => <option key={direction} value={direction}>{formatLabel(direction)}</option>)}
                    </Select>
                  </FormField>
                  <FormField htmlFor={`road-${index}-width`} label="Road width">
                    <Input disabled={!canEdit} id={`road-${index}-width`} inputMode="decimal" {...form.register(`roadSides.${index}.roadWidth`)} />
                  </FormField>
                  <FormField htmlFor={`road-${index}-edge`} label="Boundary edge index">
                    <Input disabled={!canEdit} id={`road-${index}-edge`} inputMode="numeric" {...form.register(`roadSides.${index}.boundaryEdgeIndex`)} />
                  </FormField>
                  <FormField className="sm:col-span-2" htmlFor={`road-${index}-name`} label="Road name">
                    <Input disabled={!canEdit} id={`road-${index}-name`} {...form.register(`roadSides.${index}.roadName`)} />
                  </FormField>
                  <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4 sm:col-span-2">
                    <div className="flex flex-wrap gap-5 text-sm">
                      <label className="flex items-center gap-2"><input aria-label={`Make ${road.label || `road side ${index + 1}`} the primary road`} checked={watchedRoadSides[index]?.isPrimary ?? false} className="size-4 accent-primary" disabled={!canEdit} name="primary-road" onChange={() => form.setValue("roadSides", form.getValues("roadSides").map((value, roadIndex) => ({ ...value, isPrimary: roadIndex === index })), { shouldDirty: true })} type="radio" />Primary road</label>
                      <label className="flex items-center gap-2"><input disabled={!canEdit} className="size-4 accent-primary" type="checkbox" {...form.register(`roadSides.${index}.accessAllowed`)} />Vehicle access allowed</label>
                    </div>
                    {canEdit ? <Button onClick={() => roads.remove(index)} size="sm" type="button" variant="ghost"><X aria-hidden="true" />Remove</Button> : null}
                  </div>
                </div>
              ))}
              {!roads.fields.length ? <p className="border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">No road sides recorded.</p> : null}
            </div>
          </Panel>

          <Panel className="p-5 sm:p-6">
            <SectionHeader description="Form-based boundary input with an immutable version on save." title="Plot boundary" />
            <div className="mt-5 grid gap-5 lg:grid-cols-2">
              <div className="space-y-5">
                <FormField htmlFor="coordinateSpace" label="Coordinate space">
                  <Select
                    disabled={!canEdit}
                    id="coordinateSpace"
                    {...form.register("coordinateSpace", {
                      onChange: () => {
                        form.setValue("boundarySource", "manual_vertices");
                        setBoundaryDirty(true);
                      },
                    })}
                  >
                    <option value="local_cartesian">Local Cartesian</option>
                    <option value="wgs84">WGS84 longitude / latitude</option>
                  </Select>
                </FormField>
                <BoundaryPreview coordinateSpace={watchedCoordinateSpace} vertices={watchedVertices} />
                {plot.boundary && canEdit ? <Button onClick={() => setClearingBoundary(true)} type="button" variant="ghost"><Trash2 aria-hidden="true" />Clear boundary</Button> : null}
              </div>
              <div className="space-y-4">
                <div className="flex items-center justify-between gap-3">
                  <div><h3 className="text-sm font-semibold">Vertices</h3><p className="mt-1 text-xs text-muted-foreground">Use X/Y or longitude/latitude according to coordinate space.</p></div>
                  {canEdit ? <Button onClick={() => { vertices.append({ x: "", y: "" }); form.setValue("boundarySource", "manual_vertices"); setBoundaryDirty(true); }} size="sm" type="button" variant="outline"><Plus aria-hidden="true" />Add vertex</Button> : null}
                </div>
                <div className="space-y-2">
                  {vertices.fields.map((vertex, index) => (
                    <div className="grid grid-cols-[2rem_minmax(0,1fr)_minmax(0,1fr)_auto] items-center gap-2" key={vertex.id}>
                      <span className="text-xs tabular-nums text-muted-foreground">{index + 1}</span>
                      <Input aria-label={`Vertex ${index + 1} X`} disabled={!canEdit} inputMode="decimal" {...form.register(`vertices.${index}.x`, { onChange: () => { form.setValue("boundarySource", "manual_vertices"); setBoundaryDirty(true); } })} />
                      <Input aria-label={`Vertex ${index + 1} Y`} disabled={!canEdit} inputMode="decimal" {...form.register(`vertices.${index}.y`, { onChange: () => { form.setValue("boundarySource", "manual_vertices"); setBoundaryDirty(true); } })} />
                      {canEdit ? <Button aria-label={`Remove vertex ${index + 1}`} onClick={() => { vertices.remove(index); form.setValue("boundarySource", "manual_vertices"); setBoundaryDirty(true); }} size="icon" type="button" variant="ghost"><X aria-hidden="true" /></Button> : null}
                    </div>
                  ))}
                  {!vertices.fields.length ? <p className="border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">No boundary vertices yet.</p> : null}
                </div>
              </div>
            </div>
            {canEdit ? <div className="mt-6 border-t border-border pt-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="text-sm font-semibold">GeoJSON import</h3><p className="mt-1 text-xs text-muted-foreground">Use one Polygon exterior ring. Feature wrappers are accepted.</p></div><div className="flex gap-2"><input accept="application/geo+json,application/json,.geojson,.json" aria-label="Choose a GeoJSON boundary file" className="sr-only" onChange={(event) => void readGeoJsonFile(event)} ref={fileInputRef} type="file" /><Button onClick={() => fileInputRef.current?.click()} size="sm" type="button" variant="outline"><Upload aria-hidden="true" />Choose file</Button><Button onClick={() => applyGeoJsonText()} size="sm" type="button" variant="outline"><FileJson aria-hidden="true" />Apply JSON</Button></div></div><Textarea className="mt-4 font-mono text-xs" disabled={!canEdit} placeholder='{"type":"Polygon","coordinates":[...]}' {...form.register("geoJsonText")} /></div> : null}
          </Panel>

          <Panel className="p-5 sm:p-6">
            <SectionHeader description="Every restore creates a new immutable version." title="Boundary history" />
            {historyQuery.isLoading ? <div className="mt-5 space-y-3">{Array.from({ length: 3 }, (_, index) => <Skeleton className="h-14 w-full" key={index} />)}</div> : null}
            {historyQuery.isError ? <div className="mt-5"><Button onClick={() => historyQuery.refetch()} variant="outline">Retry history</Button></div> : null}
            {historyQuery.data?.boundaries.length ? <ol className="mt-5 divide-y divide-border border-y border-border">{historyQuery.data.boundaries.map((boundary) => <li className="flex flex-wrap items-center justify-between gap-4 py-3" key={boundary.id}><div className="min-w-0"><p className="text-sm font-medium">Version {boundary.version} {boundary.isTombstone ? "(cleared)" : ""}</p><p className="mt-1 text-xs text-muted-foreground">{formatLabel(boundary.source)} | {new Date(boundary.createdAt).toLocaleString()}</p></div>{canEdit && boundary.id !== plot.boundary?.id ? <Button onClick={() => setRestoring(boundary)} size="sm" type="button" variant="outline"><History aria-hidden="true" />Restore</Button> : null}</li>)}</ol> : null}
            {!historyQuery.isLoading && !historyQuery.data?.boundaries.length ? <p className="mt-5 text-sm text-muted-foreground">Boundary versions appear after the first saved boundary.</p> : null}
          </Panel>
        </div>

        <div className="space-y-5 xl:col-span-4">
          {activeAnalysis ? <PlotAnalysisPanel analysis={activeAnalysis} unitSystem={watchedUnitSystem} /> : <PlotAnalysisSkeleton />}
          {canEdit ? <Button className="w-full" onClick={() => void recalculate()} type="button" variant="outline"><RefreshCw aria-hidden="true" />Recalculate analysis</Button> : null}
        </div>
      </div>

      <ConfirmDialog
        confirmLabel="Restore boundary"
        description={
          restoring
            ? `Restore boundary version ${restoring.version}? The current boundary can be undone for five minutes.`
            : "Restore this boundary version?"
        }
        onConfirm={() => void restoreBoundary()}
        onOpenChange={(open) => {
          if (!open) setRestoring(null);
        }}
        open={restoring !== null}
        title="Restore boundary version?"
      />
      <ConfirmDialog
        confirmLabel="Clear boundary"
        description="This creates an immutable cleared-boundary version. Previous versions remain in history."
        destructive
        onConfirm={() => void clearBoundary()}
        onOpenChange={setClearingBoundary}
        open={clearingBoundary}
        title="Clear current boundary?"
      />
    </form>
  );
}

function PlotProfileSkeleton() {
  return <div className="space-y-6"><Skeleton className="h-28 w-full" /><div className="grid gap-6 xl:grid-cols-12"><div className="space-y-6 xl:col-span-8"><Skeleton className="h-80 w-full" /><Skeleton className="h-[620px] w-full" /></div><Skeleton className="h-[460px] w-full xl:col-span-4" /></div></div>;
}

function PlotAnalysisSkeleton() {
  return <div className="space-y-5"><Skeleton className="h-52 w-full" /><Skeleton className="h-60 w-full" /><Skeleton className="h-72 w-full" /></div>;
}
