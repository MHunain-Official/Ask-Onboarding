"use client";

import { Loader2, ShieldCheck, UserRound, Users } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { ErrorBanner } from "@/components/ErrorBanner";
import { RoleBadge } from "@/components/RoleBadge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ThemeToggle } from "@/components/ThemeToggle";
import { login } from "@/lib/api";
import type { UserRole } from "@/lib/types";

const DEMO_USERS = [
  {
    email: "employee@demo.local",
    name: "Demo Employee",
    role: "employee" as UserRole,
    icon: UserRound,
    blurb: "Sees company-wide documents only.",
  },
  {
    email: "manager@demo.local",
    name: "Demo Manager",
    role: "manager" as UserRole,
    icon: Users,
    blurb: "Also sees manager-only documents.",
  },
  {
    email: "admin@demo.local",
    name: "Demo Admin",
    role: "admin" as UserRole,
    icon: ShieldCheck,
    blurb: "Everything, plus the audit dashboard.",
  },
];

// Only follow same-site relative paths so ?next= cannot become an open redirect.
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
      <ul className="grid gap-3">
        {DEMO_USERS.map(({ email, name, role, icon: Icon, blurb }) => (
          <li key={email}>
            <button
              type="button"
              disabled={pendingEmail !== null}
              onClick={() => void signIn(email)}
              className="flex w-full items-center gap-4 rounded-lg border bg-card p-4 text-left outline-none transition-colors hover:border-ring hover:bg-accent/50 focus-visible:ring-3 focus-visible:ring-ring/60 disabled:opacity-60"
            >
              <span className="flex size-10 items-center justify-center rounded-full bg-accent text-accent-foreground">
                {pendingEmail === email ? (
                  <Loader2 className="size-5 animate-spin" aria-hidden="true" />
                ) : (
                  <Icon className="size-5" aria-hidden="true" />
                )}
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-2">
                  <span className="font-medium">{name}</span>
                  <RoleBadge role={role} />
                </span>
                <span className="block text-sm text-muted-foreground">{blurb}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function LoginPage() {
  return (
    <main className="relative flex min-h-dvh items-center justify-center p-4">
      <div className="absolute top-3 right-3">
        <ThemeToggle />
      </div>
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="font-heading text-2xl">
            Ask <span className="text-ring">Onboarding</span>
          </CardTitle>
          <CardDescription>
            Answers about the company, only from its documents, with sources. Choose a demo account
            to continue.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <Suspense fallback={null}>
            <LoginForm />
          </Suspense>
          <p className="text-xs text-muted-foreground">
            Demo only: these accounts have no password. A real deployment would use company single
            sign-on.
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
