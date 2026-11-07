"use client";

import { LogOut, Menu, MessageSquare, ShieldCheck, Ticket, Upload } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { RoleBadge } from "@/components/RoleBadge";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/chat", label: "Ask", icon: MessageSquare, adminOnly: false },
  { href: "/upload", label: "Documents", icon: Upload, adminOnly: false },
  { href: "/tickets", label: "Tickets", icon: Ticket, adminOnly: false },
  { href: "/admin", label: "Admin", icon: ShieldCheck, adminOnly: true },
];

function BrandMark({ className }: { className?: string }) {
  return (
    <Link
      href="/chat"
      className={cn(
        "font-heading text-lg font-semibold tracking-tight outline-none focus-visible:ring-3 focus-visible:ring-ring/60",
        className,
      )}
    >
      Ask <span className="text-ring">Onboarding</span>
    </Link>
  );
}

function NavLinks({ onNavigate, vertical }: { onNavigate?: () => void; vertical?: boolean }) {
  const pathname = usePathname();
  const { user } = useAuth();
  const items = NAV_ITEMS.filter((item) => !item.adminOnly || user.role === "admin");

  return (
    <nav aria-label="Main" className={cn("flex gap-1", vertical ? "flex-col" : "rounded-full border bg-card/70 p-1 backdrop-blur")}>
      {items.map(({ href, label, icon: Icon }) => {
        const active = pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-2 rounded-full px-3.5 py-1.5 text-sm font-medium outline-none transition-all",
              "focus-visible:ring-3 focus-visible:ring-ring/60",
              vertical && "rounded-xl",
              active
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            <Icon className="size-4" aria-hidden="true" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, signOut } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="flex h-dvh flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:m-2 focus:rounded-md focus:bg-primary focus:px-3 focus:py-2 focus:text-primary-foreground"
      >
        Skip to content
      </a>
      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border/70 bg-card/70 px-3 backdrop-blur-md sm:px-5">
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden"
          onClick={() => setMenuOpen(true)}
          aria-label="Open navigation"
        >
          <Menu aria-hidden="true" />
        </Button>
        <BrandMark />
        <div className="ml-3 hidden md:block">
          <NavLinks />
        </div>
        <div className="ml-auto flex items-center gap-2">
          <div className="hidden items-center gap-2 sm:flex">
            <span className="max-w-36 truncate text-sm text-muted-foreground">{user.name}</span>
            <RoleBadge role={user.role} />
          </div>
          <ThemeToggle />
          <Button variant="outline" size="sm" className="rounded-full" onClick={() => void signOut()}>
            <LogOut aria-hidden="true" />
            <span className="hidden sm:inline">Sign out</span>
          </Button>
        </div>
      </header>

      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetContent side="left" className="w-72">
          <SheetHeader>
            <SheetTitle>
              <BrandMark />
            </SheetTitle>
          </SheetHeader>
          <div className="px-3 pt-2">
            <NavLinks vertical onNavigate={() => setMenuOpen(false)} />
          </div>
        </SheetContent>
      </Sheet>

      <main
        id="main"
        className={cn(
          "min-h-0 flex-1",
          // Admin Docs is a full-bleed split pane; other pages scroll inside main.
          pathname.startsWith("/admin") ? "overflow-hidden" : "overflow-y-auto",
        )}
      >
        {children}
      </main>
    </div>
  );
}
