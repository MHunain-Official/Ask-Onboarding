"use client";

import { createContext, useContext } from "react";

import type { User } from "@/lib/types";

interface AuthValue {
  user: User;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

export const AuthProvider = AuthContext.Provider;

// Only used under the (app) layout, which renders children after /api/auth/me succeeded.
export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside the signed-in app layout");
  return value;
}
