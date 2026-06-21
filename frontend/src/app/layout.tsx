import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "OI Lens — Option Intelligence Platform",
  description: "Professional options derivatives analytics for NIFTY & BANKNIFTY. Live PCR, Market State, Support/Resistance, and Insights.",
};

import { MarketDataProvider } from "@/context/MarketDataContext";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`h-full ${inter.variable} ${jetbrainsMono.variable}`}>
      <body className="min-h-full bg-[#060810] text-slate-100 antialiased font-sans">
        <MarketDataProvider>
          {children}
        </MarketDataProvider>
      </body>
    </html>
  );
}
