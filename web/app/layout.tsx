import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Clinibrium Listen",
  description:
    "Voice-first clinical decision support for vertigo. Research prototype — not for clinical use.",
};

export const DISCLAIMER =
  "Research prototype · Not for clinical use · The physician decides.";

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="es"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-background text-foreground">
        {children}
        <footer
          role="note"
          className="border-t px-4 py-3 text-center text-xs text-muted-foreground"
        >
          {DISCLAIMER}
        </footer>
      </body>
    </html>
  );
}
