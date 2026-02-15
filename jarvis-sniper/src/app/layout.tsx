import type { Metadata } from 'next';
import '@fontsource/dm-sans/400.css';
import '@fontsource/dm-sans/500.css';
import '@fontsource/dm-sans/700.css';
import '@fontsource/jetbrains-mono/400.css';
import '@fontsource/jetbrains-mono/700.css';
import './globals.css';
import { WalletProvider } from '@/components/providers/WalletProvider';
import { SniperAutomationOrchestrator } from '@/components/providers/SniperAutomationOrchestrator';
import { ResponsiveToaster } from '@/components/ResponsiveToaster';

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
      <body className="bg-bg-primary text-text-primary antialiased overflow-x-hidden">
        <WalletProvider>
          <ResponsiveToaster />
          <SniperAutomationOrchestrator />
          {/* Ambient Background */}
          <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
            {/* Keep the vibe, but tone down the blur on mobile to avoid scroll stutter. */}
            <div className="ambient-orb absolute top-1/4 left-1/4 w-72 h-72 lg:w-96 lg:h-96 bg-accent-neon/[0.03] lg:bg-accent-neon/[0.04] rounded-full blur-[96px] lg:blur-[128px]" />
            <div className="ambient-orb-2 absolute bottom-1/3 right-1/4 w-64 h-64 lg:w-80 lg:h-80 bg-accent-neon/[0.02] lg:bg-accent-neon/[0.03] rounded-full blur-[96px] lg:blur-[128px]" />
            <div className="ambient-orb-3 absolute top-2/3 left-1/2 w-56 h-56 lg:w-64 lg:h-64 bg-accent-success/[0.015] lg:bg-accent-success/[0.02] rounded-full blur-[96px] lg:blur-[128px]" />
          </div>
          <div className="relative z-10 flex min-h-screen flex-col">
            {children}
          </div>
        </WalletProvider>
      </body>
    </html>
  );
}
