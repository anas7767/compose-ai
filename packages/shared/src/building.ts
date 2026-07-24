export type UnitSystem = "metric" | "imperial";

export type Direction =
  | "north"
  | "north_east"
  | "east"
  | "south_east"
  | "south"
  | "south_west"
  | "west"
  | "north_west";

export type PlotShape = "rectangle" | "square" | "l_shape" | "irregular";

export type ConstructionQuality = "economy" | "standard" | "premium" | "luxury";

export type VastuPriority = "none" | "low" | "medium" | "strict";

export interface MoneyRange {
  min: number | null;
  max: number | null;
  currency: string;
}

export interface SiteSummary {
  city: string | null;
  state: string | null;
  country: string;
  plotWidth: number | null;
  plotDepth: number | null;
  plotArea: number | null;
  unitSystem: UnitSystem;
  roadFacingDirection: Direction | null;
  plotShape: PlotShape;
}
