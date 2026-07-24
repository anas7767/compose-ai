"use client";

import { OrganizationSwitcher } from "@clerk/nextjs";

import { AppNavigation } from "@/components/layout/app-navigation";
import { ComposeBrand } from "@/components/layout/compose-brand";
import { Separator } from "@/components/ui/separator";
import { Sheet } from "@/components/ui/sheet";

interface MobileNavigationProps {
  onOpenChange: (open: boolean) => void;
  open: boolean;
}

export function MobileNavigation({ onOpenChange, open }: MobileNavigationProps) {
  return (
    <Sheet
      description="Navigate the Compose AI workspace"
      onOpenChange={onOpenChange}
      open={open}
      title="Compose AI"
    >
      <div className="px-4 py-4">
        <ComposeBrand />
      </div>
      <Separator className="bg-sidebar-border" />
      <div className="px-4 py-4">
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
      <div className="flex-1 overflow-y-auto px-4 py-5">
        <AppNavigation onNavigate={() => onOpenChange(false)} />
      </div>
    </Sheet>
  );
}
