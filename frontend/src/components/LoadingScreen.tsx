import { useState, useEffect } from 'react';

const TIPS = [
  'Connecting to your properties...',
  'Pulling occupancy metrics...',
  'Loading leasing pipeline...',
  'Syncing market data...',
  'Crunching the numbers...',
  'Almost there...',
];

interface LoadingScreenProps {
  ready: boolean;
  /** Minimum time (ms) to show the loading screen even if data is ready */
  minDisplayMs?: number;
}

export function LoadingScreen({ ready, minDisplayMs = 1800 }: LoadingScreenProps) {
  const [tipIdx, setTipIdx] = useState(0);
  const [fadeOut, setFadeOut] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [minElapsed, setMinElapsed] = useState(false);

  // Rotate tips
  useEffect(() => {
    const id = setInterval(() => setTipIdx(i => (i + 1) % TIPS.length), 2400);
    return () => clearInterval(id);
  }, []);

  // Minimum display timer
  useEffect(() => {
    const id = setTimeout(() => setMinElapsed(true), minDisplayMs);
    return () => clearTimeout(id);
  }, [minDisplayMs]);

  // Trigger fade-out when both ready AND minimum time elapsed
  useEffect(() => {
    if (ready && minElapsed && !fadeOut) {
      setFadeOut(true);
      const id = setTimeout(() => setHidden(true), 700);
      return () => clearTimeout(id);
    }
  }, [ready, minElapsed, fadeOut]);

  if (hidden) return null;

  return (
    <div
      className={`fixed inset-0 z-[9999] flex items-center justify-center transition-opacity duration-700 ${
        fadeOut ? 'opacity-0 pointer-events-none' : 'opacity-100'
      }`}
      style={{
        backgroundImage: 'url(/venn-bg.png)',
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }}
    >
      {/* Dark overlay for contrast */}
      <div className="absolute inset-0 bg-slate-900/70 backdrop-blur-sm" />

      <div className="relative z-10 flex flex-col items-center gap-8">
        {/* Animated GIF in pill */}
        <div className="flex h-[60px] items-center rounded-full shadow-[0px_5px_30px_rgba(0,0,0,0.25)] bg-white/95 backdrop-blur">
          <img
            src="/venn-loading.gif"
            alt="Venn Intelligence"
            className="h-full w-auto"
          />
        </div>

        {/* Progress bar */}
        <div className="w-64 h-1 bg-white/10 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-indigo-400 rounded-full transition-all duration-1000 ease-out"
            style={{ width: ready && minElapsed ? '100%' : ready ? '90%' : minElapsed ? '85%' : '60%' }}
          />
        </div>

        {/* Rotating tip */}
        <p className="text-white/70 text-sm font-medium tracking-wide animate-pulse">
          {TIPS[tipIdx]}
        </p>
      </div>
    </div>
  );
}
