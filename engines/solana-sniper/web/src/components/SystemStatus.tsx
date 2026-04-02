'use client';

import { useEffect, useState } from 'react';

export function SystemStatus() {
  const [time, setTime] = useState('');

  useEffect(() => {
    const update = () => setTime(new Date().toLocaleTimeString());
    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex items-center gap-4 text-xs text-[var(--text-muted)]">
      <div className="flex items-center gap-1.5">
        <div className="w-1.5 h-1.5 rounded-full bg-[#22c55e] pulse-green" />
        <span>Raydium</span>
      </div>
      <div className="flex items-center gap-1.5">
        <div className="w-1.5 h-1.5 rounded-full bg-[#22c55e] pulse-green" />
        <span>PumpFun</span>
      </div>
      <div className="flex items-center gap-1.5">
        <div className="w-1.5 h-1.5 rounded-full bg-[#eab308]" />
        <span>Twitter</span>
      </div>
      <div className="mono text-[var(--text-secondary)]">{time}</div>
    </div>
  );
}
