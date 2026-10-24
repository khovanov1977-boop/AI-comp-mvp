import "./globals.css";
import Link from "next/link";
import type { ReactNode } from "react";
import { AuthProvider } from "../components/AuthProvider";
import { SiteNav } from "../components/AppChrome";

export const metadata = {
  title: "AI Companion — пространство для общения",
  description: "Создавайте персонажей, общайтесь и сохраняйте моменты.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru" data-scroll-behavior="smooth">
      <body><AuthProvider><SiteNav />{children}<footer className="site-footer"><span>© 2026 AI Companion</span><nav aria-label="Правовая информация"><Link href="/privacy">Обработка данных</Link><Link href="/consent">Согласие</Link><a href="mailto:xaa1@rambler.ru">Контакт</a></nav></footer></AuthProvider></body>
    </html>
  );
}
