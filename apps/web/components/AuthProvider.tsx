"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { getMe, loginAccount, logoutAccount, registerAccount, type AccountUser } from "../lib/api";

type AuthContextValue = {
  user: AccountUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AccountUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getMe().then(setUser).catch(() => setUser(null)).finally(() => setLoading(false));
    const unauthorized = () => setUser(null);
    window.addEventListener("ai-comp:unauthorized", unauthorized);
    return () => window.removeEventListener("ai-comp:unauthorized", unauthorized);
  }, []);

  async function login(email: string, password: string) { setUser(await loginAccount(email, password)); }
  async function register(email: string, password: string, name: string) { setUser(await registerAccount(email, password, name)); }
  async function logout() { await logoutAccount(); setUser(null); }

  return <AuthContext.Provider value={{ user, loading, login, register, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("AuthProvider is missing");
  return context;
}
