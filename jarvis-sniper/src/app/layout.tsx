import type { Metadata } from "next";
import { DM_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { WalletProvider } from "@/components/providers/WalletProvider";

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
  title: "Jarvis Sniper | Autonomous Token Sniper",
  description: "Autonomous Solana token sniper with Bags.fm graduation detection, auto-execution, and self-improving strategies.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{
          __html: `(function(){try{var t=localStorage.getItem('jarvis-sniper-theme');if(t==='light')document.documentElement.setAttribute('data-theme','light')}catch(e){}})()`,
        }} />
        <link href="https://api.fontshare.com/v2/css?f[]=clash-display@500,600,700&display=swap" rel="stylesheet" />
      </head>
      <body className={`${dmSans.variable} ${jetbrainsMono.variable} bg-bg-primary text-text-primary antialiased overflow-x-hidden`}>
        <WalletProvider>
          {/* Ambient Background */}
          <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
            <div className="ambient-orb absolute top-1/4 left-1/4 w-96 h-96 bg-accent-neon/[0.04] rounded-full blur-[128px]" />
            <div className="ambient-orb-2 absolute bottom-1/3 right-1/4 w-80 h-80 bg-accent-neon/[0.03] rounded-full blur-[128px]" />
            <div className="ambient-orb-3 absolute top-2/3 left-1/2 w-64 h-64 bg-accent-success/[0.02] rounded-full blur-[128px]" />
          </div>
          <div className="relative z-10 flex min-h-screen flex-col">
            {children}
          </div>
        </WalletProvider>
      </body>
    </html>
  );
}
