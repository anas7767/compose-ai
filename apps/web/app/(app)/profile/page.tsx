import { UserProfile } from "@clerk/nextjs";

export default function ProfilePage() {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-medium uppercase text-primary">Profile</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-normal">Account settings</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
          Manage your Compose AI sign-in methods, profile, sessions, and security settings.
        </p>
      </div>
      <UserProfile routing="path" path="/profile" />
    </div>
  );
}
