import type { Metadata } from "next";
import { DM_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { WalletContextProvider } from '@/components/providers/WalletContextProvider';
import { TradingProvider } from '@/context/TradingContext';
import { ThemeProvider } from '@/context/ThemeContext';
import { ToastProvider } from '@/components/ui/Toast';
import { HolographicField } from "@/components/visuals/HolographicField";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { Buffer } from "buffer";

// Polyfill for Solana Web3.js
if (typeof globalThis !== 'undefined') {
  globalThis.Buffer = Buffer;
}

const dmSans = DM_Sans({
  variable: "--font-dm-sans",
  subsets: ["latin"],
  weight: ["400", "500", "700"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Jarvis Control Deck | KR8TIV AI",
  description: "Premium trading terminal with real-time Solana intelligence, Bags.fm graduations, and advanced analytics.",
  keywords: ["solana", "trading", "bags.fm", "crypto", "defi", "terminal"],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-theme="light" suppressHydrationWarning>
      <head>
        <link href="https://api.fontshare.com/v2/css?f[]=clash-display@500,600,700&display=swap" rel="stylesheet" />
      </head>
      <body
        className={`${dmSans.variable} ${jetbrainsMono.variable} bg-bg-primary text-text-primary antialiased overflow-x-hidden`}
      >
        <ThemeProvider>
          <WalletContextProvider>
            <TradingProvider>
              <ToastProvider>
                <HolographicField />
                <div className="relative z-10 flex min-h-screen flex-col">
                  <Header />
                  <main className="flex-1 w-full max-w-[1920px] mx-auto px-2 sm:px-3 lg:px-4 py-2 relative">
                    {children}
                  </main>
                  <Footer />
                </div>
              </ToastProvider>
            </TradingProvider>
          </WalletContextProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
