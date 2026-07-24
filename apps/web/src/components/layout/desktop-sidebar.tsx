"use client";

import { OrganizationSwitcher } from "@clerk/nextjs";

import { AppNavigation } from "@/components/layout/app-navigation";
import { ComposeBrand } from "@/components/layout/compose-brand";
import { Separator } from "@/components/ui/separator";

export function DesktopSidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-40 hidden w-[248px] flex-col border-r border-sidebar-border bg-sidebar lg:flex">
      <div className="flex h-16 shrink-0 items-center px-4">
        <ComposeBrand />
      </div>
      <Separator className="bg-sidebar-border" />
      <div className="px-3 py-4">
        <OrganizationSwitcher
          afterCreateOrganizationUrl="/dashboard"
          afterLeaveOrganizationUrl="/dashboard"
          afterSelectOrganizationUrl="/dashboard"
          afterSelectPersonalUrl="/dashboard"
          appearance={{
            elements: {
              rootBox: "w-full",
              organizationSwitcherTrigger:
                "w-full justify-between rounded-md border border-sidebar-border bg-secondary/50 px-3 py-2 text-sidebar-foreground hover:bg-secondary",
            },
          }}
          hidePersonal={false}
        />
      </div>
      <Separator className="bg-sidebar-border" />
      <div className="flex-1 overflow-y-auto px-3 py-5">
        <AppNavigation />
      </div>
      <div className="border-t border-sidebar-border px-4 py-4">
        <p className="text-xs font-medium text-sidebar-foreground">Building workspace</p>
        <p className="mt-1 text-xs text-muted-foreground">Secure organization context</p>
      </div>
    </aside>
  );
}
