import type { Metadata } from "next";
import { Geist_Mono, Instrument_Sans, Newsreader } from "next/font/google";
import { Providers } from "@/components/providers";
import "./globals.css";

// UI: Instrument Sans (the instrument). Reading: Newsreader, a serif reserved for
// clinical language people say or write (transcript, questions, explanation, letter).
const uiSans = Instrument_Sans({
  variable: "--font-ui",
  subsets: ["latin"],
});

const readSerif = Newsreader({
  variable: "--font-read",
  subsets: ["latin"],
  style: ["normal", "italic"],
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
      className={`${uiSans.variable} ${readSerif.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-background text-foreground">
        <Providers>{children}</Providers>
        <footer
          role="note"
          className="border-t px-4 py-3 print:border-0 text-center text-xs text-muted-foreground"
        >
          {DISCLAIMER}
        </footer>
      </body>
    </html>
  );
}
