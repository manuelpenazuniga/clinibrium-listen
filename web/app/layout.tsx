import type { Metadata } from "next";
import {
  Atkinson_Hyperlegible_Mono,
  Atkinson_Hyperlegible_Next,
  Literata,
} from "next/font/google";
import { Providers } from "@/components/providers";
import "./globals.css";

// UI: Atkinson Hyperlegible Next, drawn for low-vision readers by the Braille
// Institute: every glyph is unambiguous (1 l I, 0 O, rn m), which matters for
// ages, minutes and doses read at a glance in a busy emergency room.
// Reading: Literata, a screen-reading serif with optical sizes, reserved for
// clinical language people say or write (transcript, questions, explanation, letter).
// Data: Atkinson Hyperlegible Mono for timestamps, rule ids and hashes.
const uiSans = Atkinson_Hyperlegible_Next({
  variable: "--font-ui",
  subsets: ["latin"],
});

const readSerif = Literata({
  variable: "--font-read",
  subsets: ["latin"],
  style: ["normal", "italic"],
  axes: ["opsz"],
});

const dataMono = Atkinson_Hyperlegible_Mono({
  variable: "--font-data",
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
      lang="en"
      className={`${uiSans.variable} ${readSerif.variable} ${dataMono.variable} h-full antialiased`}
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
