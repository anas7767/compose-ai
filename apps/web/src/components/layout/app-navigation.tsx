"use client";

import {
  CircleUserRound,
  FolderKanban,
  LayoutDashboard,
  type LucideIcon,
  UsersRound,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

interface NavigationItem {
  href: string;
  icon: LucideIcon;
  label: string;
}

interface NavigationGroup {
  items: NavigationItem[];
  label: string;
}

const navigationGroups: NavigationGroup[] = [
  {
    label: "Workspace",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/projects", label: "Projects", icon: FolderKanban },
    ],
  },
  {
    label: "Account",
    items: [
      { href: "/organization", label: "Organization", icon: UsersRound },
      { href: "/profile", label: "Profile", icon: CircleUserRound },
    ],
  },
];

export function getPageTitle(pathname: string): string {
  const item = navigationGroups
    .flatMap((group) => group.items)
    .find(
      (navigationItem) =>
        pathname === navigationItem.href || pathname.startsWith(`${navigationItem.href}/`),
    );

  return item?.label ?? "Workspace";
}

interface AppNavigationProps {
  onNavigate?: () => void;
}

export function AppNavigation({ onNavigate }: AppNavigationProps) {
  const pathname = usePathname();

  return (
    <nav aria-label="Primary navigation" className="space-y-6">
      {navigationGroups.map((group) => (
        <div key={group.label}>
          <p className="mb-2 px-3 text-xs font-medium text-muted-foreground">{group.label}</p>
          <div className="space-y-1">
            {group.items.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);

              return (
                <Link
                  aria-current={isActive ? "page" : undefined}
                  className={cn(
                    "relative flex h-10 items-center gap-3 rounded-md px-3 text-[13px] font-medium text-muted-foreground transition-colors duration-150 hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    isActive &&
                      "bg-accent text-foreground before:absolute before:left-0 before:h-5 before:w-0.5 before:rounded-full before:bg-primary",
                  )}
                  href={item.href}
                  key={item.href}
                  onClick={onNavigate}
                >
                  <Icon aria-hidden="true" className="size-4" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );
}
