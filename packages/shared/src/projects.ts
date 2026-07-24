import type { ISODateTime, UUID } from "./api";

export type ProjectStatus = "draft" | "active" | "archived";
export type ProjectListView = "active" | "drafts" | "archived" | "trash";
export type ProjectType =
  | "residential_house"
  | "villa"
  | "apartment"
  | "commercial"
  | "office"
  | "retail"
  | "hospitality"
  | "institutional"
  | "industrial"
  | "renovation"
  | "interior_only"
  | "landscape"
  | "other";
export type UnitSystem = "metric" | "imperial";
export type PlotShape = "rectangle" | "square" | "l_shaped" | "trapezoid" | "irregular" | "other";
export type RoadDirection =
  "north" | "northeast" | "east" | "southeast" | "south" | "southwest" | "west" | "northwest";
export type ConstructionQuality = "economy" | "standard" | "premium" | "luxury";
export type VastuPreference = "not_required" | "preferred" | "strict";
export type ThumbnailSource = "placeholder" | "upload" | "ai_generated" | "floor_plan" | "render";

export interface ProjectThumbnail {
  source: ThumbnailSource;
  url: string | null;
  mimeType: string | null;
  width: number | null;
  height: number | null;
  version: number;
  generatedAt: ISODateTime | null;
  metadata: Record<string, unknown>;
}

export interface ProjectClientProfile {
  name: string | null;
  company: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
}

export interface ProjectSiteProfile {
  plotLength: number | null;
  plotWidth: number | null;
  plotArea: number | null;
  plotShape: PlotShape | null;
  roadDirectionPrimary: RoadDirection | null;
  roadDirectionSecondary: RoadDirection | null;
  openSides: number;
  cornerPlot: boolean;
  addressLine1: string | null;
  addressLine2: string | null;
  city: string | null;
  region: string | null;
  postalCode: string | null;
  latitude: number | null;
  longitude: number | null;
  boundaryStatus: "not_captured" | "captured";
  orientationDegrees: number | null;
  northRotationDegrees: number | null;
  northReference: "true" | "magnetic" | "assumed" | null;
  profileRevision: number;
}

export interface ProjectPlotSummary {
  completeness: number;
  healthScore: number;
  healthStatus: "insufficient_data" | "excellent" | "good" | "needs_review" | "invalid";
  feasibilityStatus:
    | "insufficient_data"
    | "preliminarily_feasible"
    | "constrained"
    | "invalid"
    | "professional_review_required";
  validationErrorCount: number;
  validationWarningCount: number;
  preRegulationBuildableArea: number | null;
  parkingStatus: "not_required" | "likely" | "constrained" | "indeterminate";
  analysisUpdatedAt: ISODateTime | null;
}

export interface ProjectRequirementsProfile {
  bedrooms: number;
  bathrooms: number;
  floors: number;
  parkingSpaces: number;
  budget: number | null;
  constructionQuality: ConstructionQuality | null;
  preferredStyle: string | null;
  vastuPreference: VastuPreference;
  notes: string | null;
}

export interface ProjectRoomRequirement {
  id: UUID;
  name: string;
  roomType: string | null;
  quantity: number;
  preferredFloor: number | null;
  minimumArea: number | null;
  notes: string | null;
  sortOrder: number;
}

export interface ProjectSummary {
  id: UUID;
  organizationId: UUID;
  name: string;
  status: ProjectStatus;
  projectType: ProjectType | null;
  unitSystem: UnitSystem;
  currency: string;
  country: string | null;
  wizardStep: number;
  profileCompleteness: number;
  version: number;
  thumbnail: ProjectThumbnail;
  plotSummary: ProjectPlotSummary;
  city: string | null;
  tags: string[];
  completedAt: ISODateTime | null;
  archivedAt: ISODateTime | null;
  deletedAt: ISODateTime | null;
  createdAt: ISODateTime;
  updatedAt: ISODateTime;
}

export interface ProjectDetail extends ProjectSummary {
  description: string | null;
  client: ProjectClientProfile;
  site: ProjectSiteProfile;
  requirements: ProjectRequirementsProfile;
  roomRequirements: ProjectRoomRequirement[];
  duplicateSourceId: UUID | null;
}

export interface ProjectRoomRequirementInput {
  id?: UUID;
  name: string;
  roomType?: string | null;
  quantity: number;
  preferredFloor?: number | null;
  minimumArea?: number | null;
  notes?: string | null;
  sortOrder: number;
}

export interface ProjectCreateRequest {
  name: string;
  projectType?: ProjectType | null;
  unitSystem?: UnitSystem;
  currency?: string;
  country?: string | null;
}

export interface ProjectDuplicateRequest {
  name?: string | null;
}

export interface ProjectUpdateRequest {
  name?: string;
  projectType?: ProjectType | null;
  description?: string | null;
  unitSystem?: UnitSystem;
  currency?: string;
  country?: string | null;
  wizardStep?: number;
  client?: Partial<ProjectClientProfile> | null;
  site?: Partial<ProjectSiteProfile> | null;
  requirements?: Partial<ProjectRequirementsProfile> | null;
  roomRequirements?: ProjectRoomRequirementInput[];
  tags?: string[];
}

export interface ProjectDashboardSummary {
  activeCount: number;
  draftCount: number;
  archivedCount: number;
  deletedCount: number;
  usedProjectSlots: number;
}

export interface ProjectActivity {
  id: UUID;
  projectId: UUID;
  projectName: string;
  action: string;
  actorName: string | null;
  createdAt: ISODateTime;
}
