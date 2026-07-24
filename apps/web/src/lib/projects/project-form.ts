import type {
  ProjectCreateRequest,
  ProjectDetail,
  ProjectType,
  ProjectUpdateRequest,
  UnitSystem,
} from "@compose-ai/shared";
import { z } from "zod";

export const projectTypes = [
  "residential_house",
  "villa",
  "apartment",
  "commercial",
  "office",
  "retail",
  "hospitality",
  "institutional",
  "industrial",
  "renovation",
  "interior_only",
  "landscape",
  "other",
] as const;

const optionalNumber = (minimum: number, maximum: number) =>
  z.string().refine((value) => {
    if (!value.trim()) return true;
    const number = Number(value);
    return Number.isFinite(number) && number >= minimum && number <= maximum;
  }, `Enter a number between ${minimum} and ${maximum}.`);

const optionalInteger = (minimum: number, maximum: number) =>
  z.string().refine((value) => {
    if (!value.trim()) return true;
    const number = Number(value);
    return Number.isInteger(number) && number >= minimum && number <= maximum;
  }, `Enter a whole number between ${minimum} and ${maximum}.`);

const optionalHalfStep = (minimum: number, maximum: number) =>
  z.string().refine((value) => {
    if (!value.trim()) return true;
    const number = Number(value);
    return (
      Number.isFinite(number) &&
      number >= minimum &&
      number <= maximum &&
      Number.isInteger(number * 2)
    );
  }, `Enter a number between ${minimum} and ${maximum} in increments of 0.5.`);

const roomSchema = z.object({
  id: z.string().optional(),
  minimumArea: optionalNumber(0.01, 1_000_000),
  name: z.string().trim().min(1, "Room name is required.").max(80),
  notes: z.string().max(1000),
  preferredFloor: optionalInteger(-20, 200),
  quantity: optionalInteger(1, 20),
  roomType: z.string().max(80),
});

export const projectWizardSchema = z
  .object({
    addressLine1: z.string().max(255),
    addressLine2: z.string().max(255),
    bathrooms: optionalHalfStep(0, 50),
    bedrooms: optionalInteger(0, 50),
    budget: optionalNumber(0, 99_999_999_999_999),
    city: z.string().max(120),
    clientAddress: z.string().max(1000),
    clientCompany: z.string().max(160),
    clientEmail: z.union([z.literal(""), z.string().email("Enter a valid email address.")]),
    clientName: z.string().max(160),
    clientPhone: z
      .string()
      .max(32)
      .regex(/^[0-9+().\-\s]*$/, "Use a valid phone number."),
    constructionQuality: z.enum(["", "economy", "standard", "premium", "luxury"]),
    cornerPlot: z.boolean(),
    country: z.union([
      z.literal(""),
      z.string().regex(/^[A-Z]{2}$/, "Use a two-letter country code."),
    ]),
    currency: z.string().regex(/^[A-Z]{3}$/, "Use a three-letter currency code."),
    description: z.string().max(5000),
    floors: optionalInteger(1, 100),
    latitude: optionalNumber(-90, 90),
    longitude: optionalNumber(-180, 180),
    name: z.string().trim().min(2, "Project name is required.").max(160),
    notes: z.string().max(5000),
    openSides: optionalInteger(0, 4),
    parkingSpaces: optionalInteger(0, 100),
    plotArea: optionalNumber(0.001, 10_000_000_000),
    plotLength: optionalNumber(0.001, 100_000),
    plotShape: z.enum(["", "rectangle", "square", "l_shaped", "trapezoid", "irregular", "other"]),
    plotWidth: optionalNumber(0.001, 100_000),
    postalCode: z.string().max(32),
    preferredStyle: z.string().max(80),
    projectType: z.enum(["", ...projectTypes]),
    region: z.string().max(120),
    roadDirectionPrimary: z.enum([
      "",
      "north",
      "northeast",
      "east",
      "southeast",
      "south",
      "southwest",
      "west",
      "northwest",
    ]),
    roadDirectionSecondary: z.enum([
      "",
      "north",
      "northeast",
      "east",
      "southeast",
      "south",
      "southwest",
      "west",
      "northwest",
    ]),
    roomRequirements: z.array(roomSchema).max(50),
    tags: z.string().max(320),
    unitSystem: z.enum(["metric", "imperial"]),
    vastuPreference: z.enum(["not_required", "preferred", "strict"]),
  })
  .superRefine((values, context) => {
    const hasLatitude = Boolean(values.latitude.trim());
    const hasLongitude = Boolean(values.longitude.trim());
    if (hasLatitude !== hasLongitude) {
      context.addIssue({
        code: "custom",
        message: "Latitude and longitude must be supplied together.",
        path: [hasLatitude ? "longitude" : "latitude"],
      });
    }
    const openSides = Number(values.openSides || 0);
    if (openSides > 0 && !values.roadDirectionPrimary) {
      context.addIssue({
        code: "custom",
        message: "Select a primary road direction.",
        path: ["roadDirectionPrimary"],
      });
    }
    if (values.cornerPlot && openSides < 2) {
      context.addIssue({
        code: "custom",
        message: "Corner plots require at least two open sides.",
        path: ["openSides"],
      });
    }
    if (values.cornerPlot && !values.roadDirectionSecondary) {
      context.addIssue({
        code: "custom",
        message: "Select a secondary road direction.",
        path: ["roadDirectionSecondary"],
      });
    }
    if (
      values.roadDirectionPrimary &&
      values.roadDirectionPrimary === values.roadDirectionSecondary
    ) {
      context.addIssue({
        code: "custom",
        message: "Road directions must be different.",
        path: ["roadDirectionSecondary"],
      });
    }
    const tags = values.tags
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean);
    if (tags.length > 10) {
      context.addIssue({
        code: "custom",
        message: "Use no more than 10 tags.",
        path: ["tags"],
      });
    }
    if (tags.some((tag) => tag.length > 30)) {
      context.addIssue({
        code: "custom",
        message: "Each tag must be 30 characters or fewer.",
        path: ["tags"],
      });
    }
  });

export type ProjectWizardValues = z.infer<typeof projectWizardSchema>;

export const emptyProjectValues: ProjectWizardValues = {
  addressLine1: "",
  addressLine2: "",
  bathrooms: "0",
  bedrooms: "0",
  budget: "",
  city: "",
  clientAddress: "",
  clientCompany: "",
  clientEmail: "",
  clientName: "",
  clientPhone: "",
  constructionQuality: "",
  cornerPlot: false,
  country: "",
  currency: "USD",
  description: "",
  floors: "1",
  latitude: "",
  longitude: "",
  name: "",
  notes: "",
  openSides: "0",
  parkingSpaces: "0",
  plotArea: "",
  plotLength: "",
  plotShape: "",
  plotWidth: "",
  postalCode: "",
  preferredStyle: "",
  projectType: "",
  region: "",
  roadDirectionPrimary: "",
  roadDirectionSecondary: "",
  roomRequirements: [],
  tags: "",
  unitSystem: "metric",
  vastuPreference: "not_required",
};

const numberOrNull = (value: string): number | null => (value.trim() ? Number(value) : null);
const textOrNull = (value: string): string | null => (value.trim() ? value.trim() : null);

export function projectToWizardValues(project: ProjectDetail): ProjectWizardValues {
  return {
    addressLine1: project.site.addressLine1 ?? "",
    addressLine2: project.site.addressLine2 ?? "",
    bathrooms: String(project.requirements.bathrooms),
    bedrooms: String(project.requirements.bedrooms),
    budget: project.requirements.budget === null ? "" : String(project.requirements.budget),
    city: project.site.city ?? "",
    clientAddress: project.client.address ?? "",
    clientCompany: project.client.company ?? "",
    clientEmail: project.client.email ?? "",
    clientName: project.client.name ?? "",
    clientPhone: project.client.phone ?? "",
    constructionQuality: project.requirements.constructionQuality ?? "",
    cornerPlot: project.site.cornerPlot,
    country: project.country ?? "",
    currency: project.currency,
    description: project.description ?? "",
    floors: String(project.requirements.floors),
    latitude: project.site.latitude === null ? "" : String(project.site.latitude),
    longitude: project.site.longitude === null ? "" : String(project.site.longitude),
    name: project.name,
    notes: project.requirements.notes ?? "",
    openSides: String(project.site.openSides),
    parkingSpaces: String(project.requirements.parkingSpaces),
    plotArea: project.site.plotArea === null ? "" : String(project.site.plotArea),
    plotLength: project.site.plotLength === null ? "" : String(project.site.plotLength),
    plotShape: project.site.plotShape ?? "",
    plotWidth: project.site.plotWidth === null ? "" : String(project.site.plotWidth),
    postalCode: project.site.postalCode ?? "",
    preferredStyle: project.requirements.preferredStyle ?? "",
    projectType: project.projectType ?? "",
    region: project.site.region ?? "",
    roadDirectionPrimary: project.site.roadDirectionPrimary ?? "",
    roadDirectionSecondary: project.site.roadDirectionSecondary ?? "",
    roomRequirements: project.roomRequirements.map((room) => ({
      id: room.id,
      minimumArea: room.minimumArea === null ? "" : String(room.minimumArea),
      name: room.name,
      notes: room.notes ?? "",
      preferredFloor: room.preferredFloor === null ? "" : String(room.preferredFloor),
      quantity: String(room.quantity),
      roomType: room.roomType ?? "",
    })),
    tags: project.tags.join(", "),
    unitSystem: project.unitSystem,
    vastuPreference: project.requirements.vastuPreference,
  };
}

export function wizardValuesToCreate(values: ProjectWizardValues): ProjectCreateRequest {
  return {
    country: textOrNull(values.country),
    currency: values.currency,
    name: values.name.trim(),
    projectType: (values.projectType || null) as ProjectType | null,
    unitSystem: values.unitSystem as UnitSystem,
  };
}

export function wizardValuesToUpdate(
  values: ProjectWizardValues,
  wizardStep: number,
): ProjectUpdateRequest {
  return {
    client: {
      address: textOrNull(values.clientAddress),
      company: textOrNull(values.clientCompany),
      email: textOrNull(values.clientEmail),
      name: textOrNull(values.clientName),
      phone: textOrNull(values.clientPhone),
    },
    country: textOrNull(values.country),
    currency: values.currency,
    description: textOrNull(values.description),
    name: values.name.trim(),
    projectType: (values.projectType || null) as ProjectType | null,
    requirements: {
      bathrooms: numberOrNull(values.bathrooms) ?? 0,
      bedrooms: numberOrNull(values.bedrooms) ?? 0,
      budget: numberOrNull(values.budget),
      constructionQuality: values.constructionQuality || null,
      floors: numberOrNull(values.floors) ?? 1,
      notes: textOrNull(values.notes),
      parkingSpaces: numberOrNull(values.parkingSpaces) ?? 0,
      preferredStyle: textOrNull(values.preferredStyle),
      vastuPreference: values.vastuPreference,
    },
    roomRequirements: values.roomRequirements.map((room, index) => ({
      id: room.id,
      minimumArea: numberOrNull(room.minimumArea),
      name: room.name.trim(),
      notes: textOrNull(room.notes),
      preferredFloor: numberOrNull(room.preferredFloor),
      quantity: numberOrNull(room.quantity) ?? 1,
      roomType: textOrNull(room.roomType),
      sortOrder: index,
    })),
    site: {
      addressLine1: textOrNull(values.addressLine1),
      addressLine2: textOrNull(values.addressLine2),
      city: textOrNull(values.city),
      cornerPlot: values.cornerPlot,
      latitude: numberOrNull(values.latitude),
      longitude: numberOrNull(values.longitude),
      openSides: numberOrNull(values.openSides) ?? 0,
      plotArea: numberOrNull(values.plotArea),
      plotLength: numberOrNull(values.plotLength),
      plotShape: values.plotShape || null,
      plotWidth: numberOrNull(values.plotWidth),
      postalCode: textOrNull(values.postalCode),
      region: textOrNull(values.region),
      roadDirectionPrimary: values.roadDirectionPrimary || null,
      roadDirectionSecondary: values.roadDirectionSecondary || null,
    },
    tags: values.tags
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean),
    unitSystem: values.unitSystem,
    wizardStep,
  };
}
