"use client";

import { UserButton } from "@clerk/nextjs";
import { Menu } from "lucide-react";
import { usePathname } from "next/navigation";

import { getPageTitle } from "@/components/layout/app-navigation";
import { IconButton } from "@/components/ui/icon-button";

interface TopNavigationProps {
  onOpenNavigation: () => void;
}

export function TopNavigation({ onOpenNavigation }: TopNavigationProps) {
  const pathname = usePathname();
  const pageTitle = getPageTitle(pathname);

  return (
    <header className="sticky top-0 z-30 h-16 border-b border-border bg-background/90 backdrop-blur-xl">
      <div className="flex h-full items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <div className="flex min-w-0 items-center gap-3">
          <div className="lg:hidden">
            <IconButton label="Open navigation" onClick={onOpenNavigation} variant="ghost">
              <Menu aria-hidden="true" />
            </IconButton>
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-foreground">{pageTitle}</p>
            <p className="hidden text-xs text-muted-foreground sm:block">Compose workspace</p>
          </div>
        </div>

        <UserButton
          afterSignOutUrl="/"
          appearance={{
            elements: {
              avatarBox: "size-9 ring-1 ring-border",
              userButtonPopoverCard: "border border-border bg-popover shadow-lg",
            },
          }}
        />
      </div>
    </header>
  );
}
