import { OrganizationProfile } from "@clerk/nextjs";

export default function OrganizationPage() {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-medium uppercase text-primary">Organization</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-normal">Workspace settings</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
          Manage organization members and profile details in Clerk. Compose-specific workspace
          permissions are mirrored in the API for future project access.
        </p>
      </div>
      <OrganizationProfile routing="hash" />
    </div>
  );
}
