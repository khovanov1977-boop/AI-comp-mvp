import "./globals.css";
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
      <body><AuthProvider><SiteNav />{children}</AuthProvider></body>
    </html>
  );
}
