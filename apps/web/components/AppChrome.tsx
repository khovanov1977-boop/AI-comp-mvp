"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { useAuth } from "./AuthProvider";

export function SiteNav() {
  const { user, loading, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const links = [
    { href: "/characters", label: "Персонажи" },
    { href: "/examples", label: "Примеры" },
    { href: "/gallery", label: "Медиа" },
    { href: "/account", label: "Аккаунт" },
  ];
  return <header className="site-header">
    <Link className="site-logo" href="/" aria-label="На главную"><span className="logo-mark">✳</span><span>AI Companion<span className="logo-dot">.</span></span></Link>
    {user ? <nav className="site-nav" aria-label="Основная навигация">
      {links.map((item) => <Link className={pathname.startsWith(item.href) || (item.href === "/characters" && pathname.startsWith("/chat/")) ? "active" : ""} href={item.href} key={item.href}>{item.label}</Link>)}
    </nav> : null}
    <div className="site-header-end">
      {loading ? null : user ? <><span className="account-chip" title={user.email}>{user.display_name.slice(0, 1).toUpperCase()}</span><button className="header-link" type="button" onClick={async () => { await logout(); router.push("/"); }}>Выйти</button></> : <Link className="header-link header-login" href="/login">Войти <span aria-hidden="true">→</span></Link>}
    </div>
  </header>;
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  useEffect(() => { if (!loading && !user) router.replace("/login"); }, [loading, user, router]);
  if (loading || !user) return <div className="page-loading"><span className="loading-orb" />Загружаем ваше пространство…</div>;
  return <>{children}</>;
}
