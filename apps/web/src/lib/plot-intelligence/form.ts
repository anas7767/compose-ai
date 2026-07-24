import type {
  CoordinateSpace,
  NorthReference,
  PlotBoundaryInput,
  PlotIntelligence,
  PlotProfileUpdateRequest,
  PlotRoadSideInput,
  PlotShape,
  RoadDirection,
  UnitSystem,
} from "@compose-ai/shared";

export const plotShapes: PlotShape[] = [
  "rectangle",
  "square",
  "l_shaped",
  "trapezoid",
  "irregular",
  "other",
];

export const roadDirections: RoadDirection[] = [
  "north",
  "northeast",
  "east",
  "southeast",
  "south",
  "southwest",
  "west",
  "northwest",
];

export interface PlotRoadFormValue {
  id?: string;
  boundaryEdgeIndex: string;
  label: string;
  direction: RoadDirection;
  isPrimary: boolean;
  roadName: string;
  roadWidth: string;
  accessAllowed: boolean;
  sortOrder: number;
}

export interface BoundaryVertexFormValue {
  x: string;
  y: string;
}

export interface PlotFormValues {
  unitSystem: UnitSystem;
  plotLength: string;
  plotWidth: string;
  plotArea: string;
  plotShape: PlotShape | "";
  openSides: string;
  cornerPlot: boolean;
  orientationDegrees: string;
  northRotationDegrees: string;
  northReference: NorthReference | "";
  coordinateSpace: CoordinateSpace;
  boundarySource: PlotBoundaryInput["source"];
  geoJsonText: string;
  roadSides: PlotRoadFormValue[];
  vertices: BoundaryVertexFormValue[];
}

export interface PlotFormError {
  field: string;
  message: string;
}

export function emptyPlotFormValues(): PlotFormValues {
  return {
    unitSystem: "metric",
    plotLength: "",
    plotWidth: "",
    plotArea: "",
    plotShape: "",
    openSides: "0",
    cornerPlot: false,
    orientationDegrees: "",
    northRotationDegrees: "",
    northReference: "",
    coordinateSpace: "local_cartesian",
    boundarySource: "manual_vertices",
    geoJsonText: "",
    roadSides: [],
    vertices: [],
  };
}

export function plotToFormValues(plot: PlotIntelligence): PlotFormValues {
  const geometry = plot.boundary?.geojson;
  return {
    unitSystem: plot.profile.unitSystem,
    plotLength: numberText(plot.profile.plotLength),
    plotWidth: numberText(plot.profile.plotWidth),
    plotArea: numberText(plot.profile.plotArea),
    plotShape: plot.profile.plotShape ?? "",
    openSides: String(plot.profile.openSides),
    cornerPlot: plot.profile.cornerPlot,
    orientationDegrees: numberText(plot.profile.orientationDegrees),
    northRotationDegrees: numberText(plot.profile.northRotationDegrees),
    northReference: plot.profile.northReference ?? "",
    coordinateSpace: plot.boundary?.coordinateSpace ?? "local_cartesian",
    boundarySource:
      plot.boundary?.source === "geojson_import" ? "geojson_import" : "manual_vertices",
    geoJsonText: geometry ? JSON.stringify(geometry, null, 2) : "",
    roadSides: plot.roadSides.map((road) => ({
      id: road.id,
      boundaryEdgeIndex: road.boundaryEdgeIndex === null ? "" : String(road.boundaryEdgeIndex),
      label: road.label,
      direction: road.direction,
      isPrimary: road.isPrimary,
      roadName: road.roadName ?? "",
      roadWidth: numberText(road.roadWidth),
      accessAllowed: road.accessAllowed,
      sortOrder: road.sortOrder,
    })),
    vertices: geometry ? geometry.coordinates[0].slice(0, -1).map(([x, y]) => ({ x: String(x), y: String(y) })) : [],
  };
}

export function validatePlotForm(values: PlotFormValues, boundaryDirty: boolean): PlotFormError[] {
  const errors: PlotFormError[] = [];
  const openSides = integerOrNull(values.openSides);
  if (openSides === null || openSides < 0 || openSides > 4) {
    errors.push({ field: "openSides", message: "Open sides must be a whole number from 0 to 4." });
  }
  for (const field of ["plotLength", "plotWidth", "plotArea", "orientationDegrees", "northRotationDegrees"] as const) {
    const value = values[field];
    if (value.trim() && !isFiniteNumber(value)) {
      errors.push({ field, message: "Enter a valid number." });
    }
  }
  if (values.orientationDegrees.trim()) {
    const orientation = Number(values.orientationDegrees);
    if (orientation < 0 || orientation >= 360) {
      errors.push({ field: "orientationDegrees", message: "Orientation must be from 0 to 359.999." });
    }
    if (!values.northReference) {
      errors.push({ field: "northReference", message: "Select a north reference for orientation." });
    }
  }
  if (values.cornerPlot && (openSides ?? 0) < 2) {
    errors.push({ field: "cornerPlot", message: "Corner plots require at least two open sides." });
  }
  if (values.roadSides.length > (openSides ?? 0)) {
    errors.push({ field: "roadSides", message: "Road-side count cannot exceed open-side count." });
  }
  if (values.cornerPlot && values.roadSides.length < 2) {
    errors.push({ field: "roadSides", message: "Corner plots require two road sides." });
  }
  if (values.roadSides.length && values.roadSides.filter((road) => road.isPrimary).length !== 1) {
    errors.push({ field: "roadSides", message: "Select exactly one primary road side." });
  }
  const directions = values.roadSides.map((road) => road.direction);
  if (directions.length !== new Set(directions).size) {
    errors.push({ field: "roadSides", message: "Road-side directions must be unique." });
  }
  values.roadSides.forEach((road, index) => {
    if (!road.label.trim()) {
      errors.push({ field: `roadSides.${index}.label`, message: "Road-side label is required." });
    }
    if (road.roadWidth.trim() && (!isFiniteNumber(road.roadWidth) || Number(road.roadWidth) <= 0)) {
      errors.push({ field: `roadSides.${index}.roadWidth`, message: "Road width must be positive." });
    }
  });
  if (boundaryDirty) {
    if (values.vertices.length < 3) {
      errors.push({ field: "vertices", message: "A boundary requires at least three vertices." });
    }
    values.vertices.forEach((vertex, index) => {
      if (!isFiniteNumber(vertex.x) || !isFiniteNumber(vertex.y)) {
        errors.push({ field: `vertices.${index}`, message: "Every vertex needs valid X and Y values." });
      }
    });
  }
  return errors;
}

export function plotFormToRequest(
  values: PlotFormValues,
  boundaryDirty: boolean,
): PlotProfileUpdateRequest {
  const roadSides: PlotRoadSideInput[] = values.roadSides.map((road, index) => ({
    id: road.id,
    boundaryEdgeIndex: integerOrNull(road.boundaryEdgeIndex),
    label: road.label.trim(),
    direction: road.direction,
    isPrimary: road.isPrimary,
    roadName: textOrNull(road.roadName),
    roadWidth: numberOrNull(road.roadWidth),
    accessAllowed: road.accessAllowed,
    sortOrder: index,
  }));
  return {
    unitSystem: values.unitSystem,
    plotLength: numberOrNull(values.plotLength),
    plotWidth: numberOrNull(values.plotWidth),
    plotArea: numberOrNull(values.plotArea),
    plotShape: values.plotShape || null,
    openSides: integerOrNull(values.openSides) ?? 0,
    cornerPlot: values.cornerPlot,
    orientationDegrees: numberOrNull(values.orientationDegrees),
    northRotationDegrees: numberOrNull(values.northRotationDegrees),
    northReference: values.northReference || null,
    roadSides,
    boundary: boundaryDirty
      ? {
          coordinateSpace: values.coordinateSpace,
          geojson: {
            type: "Polygon",
            coordinates: [
              closeRing(values.vertices.map((vertex) => [Number(vertex.x), Number(vertex.y)])),
            ],
          },
          source: values.boundarySource,
        }
      : undefined,
  };
}

export function convertFormValues(
  values: PlotFormValues,
  nextUnitSystem: UnitSystem,
): PlotFormValues {
  if (values.unitSystem === nextUnitSystem) return values;
  const lengthMultiplier = values.unitSystem === "metric" ? 3.280839895 : 0.3048;
  const areaMultiplier = values.unitSystem === "metric" ? 10.763910417 : 0.09290304;
  const convert = (value: string, multiplier: number) =>
    value.trim() && isFiniteNumber(value) ? String(round(Number(value) * multiplier, 4)) : value;
  return {
    ...values,
    unitSystem: nextUnitSystem,
    plotLength: convert(values.plotLength, lengthMultiplier),
    plotWidth: convert(values.plotWidth, lengthMultiplier),
    plotArea: convert(values.plotArea, areaMultiplier),
    roadSides: values.roadSides.map((road) => ({
      ...road,
      roadWidth: convert(road.roadWidth, lengthMultiplier),
    })),
    vertices:
      values.coordinateSpace === "local_cartesian"
        ? values.vertices.map((vertex) => ({
            x: convert(vertex.x, lengthMultiplier),
            y: convert(vertex.y, lengthMultiplier),
          }))
        : values.vertices,
  };
}

export function extractPolygon(value: unknown): { coordinates: number[][][] } {
  if (!value || typeof value !== "object") throw new Error("GeoJSON must be an object.");
  const candidate = value as { type?: string; geometry?: unknown; coordinates?: unknown };
  const geometry = candidate.type === "Feature" ? candidate.geometry : candidate;
  if (!geometry || typeof geometry !== "object") throw new Error("Feature geometry is required.");
  const polygon = geometry as { type?: string; coordinates?: unknown };
  if (polygon.type !== "Polygon" || !Array.isArray(polygon.coordinates) || polygon.coordinates.length !== 1) {
    throw new Error("Use one GeoJSON Polygon exterior ring without holes.");
  }
  if (!Array.isArray(polygon.coordinates[0])) throw new Error("Polygon coordinates are invalid.");
  return { coordinates: polygon.coordinates as number[][][] };
}

function numberText(value: number | null): string {
  return value === null ? "" : String(value);
}

function numberOrNull(value: string): number | null {
  return value.trim() ? Number(value) : null;
}

function integerOrNull(value: string): number | null {
  return value.trim() && Number.isInteger(Number(value)) ? Number(value) : null;
}

function textOrNull(value: string): string | null {
  return value.trim() || null;
}

function isFiniteNumber(value: string): boolean {
  return value.trim() !== "" && Number.isFinite(Number(value));
}

function closeRing(vertices: number[][]): number[][] {
  if (!vertices.length) return [];
  const first = vertices[0];
  const last = vertices[vertices.length - 1];
  return first[0] === last[0] && first[1] === last[1] ? vertices : [...vertices, first];
}

function round(value: number, precision: number): number {
  const factor = 10 ** precision;
  return Math.round(value * factor) / factor;
}
