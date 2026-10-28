import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";

export const metadata: Metadata = {
  title: { default: "AI Story Studio", template: "%s · AI Story Studio" },
  description: "Local-first studio for Vietnamese children's story videos",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi">
      <body><Providers>{children}</Providers></body>
    </html>
  );
}

