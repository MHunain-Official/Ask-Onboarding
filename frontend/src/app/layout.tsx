import type { Metadata } from "next";
import { DM_Mono, DM_Sans, Source_Serif_4 } from "next/font/google";

import { ThemeProvider } from "@/components/ThemeProvider";
import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

// Serif headings give the "company handbook" feel; DM Sans keeps UI text crisp.
const sans = DM_Sans({ variable: "--font-dm-sans", subsets: ["latin"] });
const serif = Source_Serif_4({
  variable: "--font-source-serif",
  subsets: ["latin"],
});
const mono = DM_Mono({
  variable: "--font-dm-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "Ask Onboarding",
  description: "Answers about your company, only from your company's documents.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${sans.variable} ${serif.variable} ${mono.variable} antialiased`}>
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          {children}
          <Toaster richColors closeButton />
        </ThemeProvider>
      </body>
    </html>
  );
}
