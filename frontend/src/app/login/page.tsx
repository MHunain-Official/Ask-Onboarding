"use client";

import { ArrowRight, BookOpenCheck, Loader2, ShieldCheck, UserRound, Users } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { ErrorBanner } from "@/components/ErrorBanner";
import { RoleBadge } from "@/components/RoleBadge";
import { ThemeToggle } from "@/components/ThemeToggle";
import { login } from "@/lib/api";
import type { UserRole } from "@/lib/types";
import { cn } from "@/lib/utils";

const DEMO_USERS = [
  {
    email: "employee@demo.local",
    name: "Demo Employee",
    role: "employee" as UserRole,
    icon: UserRound,
    blurb: "Company-wide handbook answers.",
  },
  {
    email: "manager@demo.local",
    name: "Demo Manager",
    role: "manager" as UserRole,
    icon: Users,
    blurb: "Plus manager-only docs and tickets.",
  },
  {
    email: "admin@demo.local",
    name: "Demo Admin",
    role: "admin" as UserRole,
    icon: ShieldCheck,
    blurb: "Full library, tickets, and audit KPIs.",
  },
];

function safeNextPath(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/chat";
}

function LoginForm() {
  const router = useRouter();
  const nextPath = safeNextPath(useSearchParams().get("next"));
  const [pendingEmail, setPendingEmail] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function signIn(email: string) {
    setPendingEmail(email);
    setError(null);
    try {
      await login(email);
      router.replace(nextPath);
    } catch {
      setError("Sign-in failed. Is the backend running and seeded with the demo users?");
      setPendingEmail(null);
    }
  }

  return (
    <div className="grid gap-3">
      {error ? <ErrorBanner message={error} /> : null}
      <ul className="grid gap-2.5">
        {DEMO_USERS.map(({ email, name, role, icon: Icon, blurb }, index) => (
          <li key={email} className={cn("animate-rise", `stagger-${index + 1}`)}>
            <button
              type="button"
              disabled={pendingEmail !== null}
              onClick={() => void signIn(email)}
              className={cn(
                "group flex w-full items-center gap-4 rounded-2xl border bg-card/80 p-4 text-left outline-none transition-all",
                "hover:-translate-y-0.5 hover:border-ring hover:bg-accent/40 hover:shadow-md",
                "focus-visible:ring-3 focus-visible:ring-ring/60 disabled:opacity-60",
              )}
            >
              <span className="flex size-11 items-center justify-center rounded-2xl bg-accent text-accent-foreground transition-colors group-hover:bg-ring group-hover:text-primary-foreground">
                {pendingEmail === email ? (
                  <Loader2 className="size-5 animate-spin" aria-hidden="true" />
                ) : (
                  <Icon className="size-5" aria-hidden="true" />
                )}
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{name}</span>
                  <RoleBadge role={role} />
                </span>
                <span className="mt-0.5 block text-sm text-muted-foreground">{blurb}</span>
              </span>
              <ArrowRight
                className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-ring"
                aria-hidden="true"
              />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function LoginPage() {
  return (
    <main className="relative flex min-h-dvh items-center justify-center overflow-hidden p-4 sm:p-8">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_1px_1px,oklch(0.45_0.03_230/0.08)_1px,transparent_0)] [background-size:22px_22px]"
      />
      <div className="absolute top-4 right-4 z-10">
        <ThemeToggle />
      </div>

      <div className="relative z-10 grid w-full max-w-5xl gap-10 lg:grid-cols-[1.05fr_0.95fr] lg:items-center lg:gap-14">
        <section className="animate-rise space-y-5 text-center lg:text-left">
          <p className="inline-flex items-center gap-2 rounded-full border bg-card/70 px-3 py-1 text-xs font-medium tracking-wide text-muted-foreground uppercase backdrop-blur">
            <BookOpenCheck className="size-3.5 text-ring" aria-hidden="true" />
            Company knowledge, cited
          </p>
          <h1 className="font-heading text-4xl leading-[1.08] font-semibold tracking-tight sm:text-5xl lg:text-[3.4rem]">
            Ask <span className="text-ring">Onboarding</span>
          </h1>
          <p className="mx-auto max-w-md text-base text-muted-foreground lg:mx-0">
            Answers only from your handbook and wiki — with the exact passage highlighted. Pick a
            demo role to try it.
          </p>
        </section>

        <section className="surface-glass animate-rise stagger-2 rounded-3xl p-5 sm:p-7">
          <div className="mb-5">
            <h2 className="font-heading text-xl font-semibold">Continue as</h2>
            <p className="text-sm text-muted-foreground">
              Demo accounts have no password. Real deployments would use company SSO.
            </p>
          </div>
          <Suspense fallback={null}>
            <LoginForm />
          </Suspense>
        </section>
      </div>
    </main>
  );
}
