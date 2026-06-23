import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "AI Companion MVP",
  description: "Sprint 0 AI Companion skeleton",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
