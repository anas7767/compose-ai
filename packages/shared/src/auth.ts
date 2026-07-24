import type { ISODateTime, UUID } from "./api";

export type OrganizationRole = "owner" | "admin" | "editor" | "viewer" | "client" | "contractor";
export type OrganizationMemberStatus = "invited" | "active" | "disabled";
export type SubscriptionStatus = "trialing" | "active" | "past_due" | "cancelled" | "free";

export interface AuthBootstrapRequest {
  email: string | null;
  name: string;
  avatarUrl: string | null;
  activeClerkOrganizationId: string | null;
  activeOrganizationName: string | null;
  activeOrganizationSlug: string | null;
  activeOrganizationRole: string | null;
}

export interface AuthUser {
  id: UUID;
  clerkUserId: string;
  email: string | null;
  name: string;
  avatarUrl: string | null;
  status: "active" | "disabled";
  lastLoginAt: ISODateTime;
}

export interface AuthOrganization {
  id: UUID;
  clerkOrganizationId: string | null;
  name: string;
  slug: string;
  type: "homeowner" | "studio" | "builder" | "enterprise" | "personal";
  planStatus: "free" | "trialing" | "active" | "past_due" | "cancelled";
}

export interface AuthMembership {
  id: UUID;
  role: OrganizationRole;
  status: OrganizationMemberStatus;
}

export interface AuthSubscription {
  id: UUID;
  planCode: "free" | string;
  status: SubscriptionStatus;
  projectLimit: number;
  aiCreditLimit: number;
  renderLimit: number;
  storageLimitMb: number;
}

export interface AuthContextResponse {
  user: AuthUser;
  organization: AuthOrganization;
  membership: AuthMembership;
  subscription: AuthSubscription;
  permissions: string[];
}

export interface AuthSessionResponse {
  clerkUserId: string;
  clerkSessionId: string | null;
  clerkOrganizationId: string | null;
  clerkOrganizationRole: string | null;
  expiresAt: number | null;
  issuedAt: number | null;
}
