"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { AuthProvider } from "@/components/AuthProvider";
import { ErrorBanner } from "@/components/ErrorBanner";
import { ApiError, getMe, logout } from "@/lib/api";
import type { User } from "@/lib/types";

// Client-side route protection: every signed-in page asks /api/auth/me first.
// (The backend still enforces auth on every API call; this is only UX.)
export default function SignedInLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadUser = useCallback(() => {
    setError(null);
    getMe()
      .then(setUser)
      .catch((caught: unknown) => {
        if (caught instanceof ApiError && caught.status === 401) {
          const next = encodeURIComponent(window.location.pathname);
          router.replace(`/login?next=${next}`);
          return;
        }
        setError("We couldn't reach the server. Check your connection and try again.");
      });
  }, [router]);

  useEffect(loadUser, [loadUser]);

  const signOut = useCallback(async () => {
    await logout().catch(() => undefined);
    router.replace("/login");
  }, [router]);

  if (error) {
    return (
      <div className="mx-auto max-w-lg p-6">
        <ErrorBanner message={error} onRetry={loadUser} />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex h-dvh items-center justify-center" role="status">
        <span className="text-sm text-muted-foreground">Checking your session…</span>
      </div>
    );
  }

  return (
    <AuthProvider value={{ user, signOut }}>
      <AppShell>{children}</AppShell>
    </AuthProvider>
  );
}
