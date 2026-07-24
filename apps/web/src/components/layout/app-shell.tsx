"use client";

import * as React from "react";

import { DesktopSidebar } from "@/components/layout/desktop-sidebar";
import { MobileNavigation } from "@/components/layout/mobile-navigation";
import { TopNavigation } from "@/components/layout/top-navigation";

export function AppShell({ children }: Readonly<{ children: React.ReactNode }>) {
  const [mobileNavigationOpen, setMobileNavigationOpen] = React.useState(false);

  return (
    <div className="min-h-dvh bg-background">
      <a
        className="fixed left-4 top-4 z-[60] -translate-y-24 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-lg transition-transform focus:translate-y-0"
        href="#main-content"
      >
        Skip to content
      </a>

      <DesktopSidebar />

      <div className="min-h-dvh lg:pl-[248px]">
        <TopNavigation onOpenNavigation={() => setMobileNavigationOpen(true)} />
        <main className="min-h-[calc(100dvh-4rem)]" id="main-content" tabIndex={-1}>
          <div className="mx-auto w-full max-w-[1440px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
            {children}
          </div>
        </main>
      </div>

      <MobileNavigation open={mobileNavigationOpen} onOpenChange={setMobileNavigationOpen} />
    </div>
  );
}
