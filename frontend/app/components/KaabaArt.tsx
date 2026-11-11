/** Иллюстрация для страницы входа: Кааба на рассвете (векторная, своя). */
export function KaabaArt({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 900 900" preserveAspectRatio="xMidYMax slice" className={className} aria-hidden="true">
      <defs>
        <linearGradient id="ka-sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#231912" />
          <stop offset="0.45" stopColor="#4a3a2c" />
          <stop offset="0.66" stopColor="#a5835a" />
          <stop offset="0.7" stopColor="#d9bf92" />
        </linearGradient>
        <linearGradient id="ka-floor" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#e9dccb" />
          <stop offset="1" stopColor="#8a755f" />
        </linearGradient>
        <radialGradient id="ka-glow" cx="0.5" cy="0.66" r="0.45">
          <stop offset="0" stopColor="#f3dfb6" stopOpacity="0.9" />
          <stop offset="1" stopColor="#f3dfb6" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="ka-front" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#15100c" />
          <stop offset="1" stopColor="#241b14" />
        </linearGradient>
        <linearGradient id="ka-band" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#a7843f" />
          <stop offset="0.5" stopColor="#e2c47a" />
          <stop offset="1" stopColor="#a7843f" />
        </linearGradient>
        <linearGradient id="ka-fade" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#1a120d" stopOpacity="0.55" />
          <stop offset="1" stopColor="#1a120d" stopOpacity="0" />
        </linearGradient>
      </defs>

      <rect width="900" height="900" fill="url(#ka-sky)" />
      <rect width="900" height="900" fill="url(#ka-glow)" />
      <rect y="596" width="900" height="304" fill="url(#ka-floor)" />
      {/* плитка пола */}
      <g stroke="#ffffff" strokeOpacity="0.18" strokeWidth="1">
        {[640, 700, 780, 880].map((y) => <line key={y} x1="0" y1={y} x2="900" y2={y} />)}
        {[-400, -200, 0, 200, 400, 600, 800, 1000, 1200, 1400].map((x) => (
          <line key={x} x1="450" y1="596" x2={x} y2="900" />
        ))}
      </g>

      {/* отражение */}
      <g opacity="0.12">
        <polygon points="350,600 520,600 520,690 350,690" fill="#15100c" />
        <polygon points="520,600 575,590 575,670 520,690" fill="#2a2018" />
      </g>

      {/* Кааба: фасад и боковая грань */}
      <polygon points="350,410 520,410 520,600 350,600" fill="url(#ka-front)" />
      <polygon points="520,410 575,390 575,590 520,600" fill="#2c221a" />
      <polygon points="350,410 405,390 575,390 520,410" fill="#2a2019" />
      {/* золотой пояс */}
      <polygon points="350,448 520,448 520,466 350,466" fill="url(#ka-band)" />
      <polygon points="520,448 575,432 575,449 520,466" fill="#9c7a3a" />
      <g fill="#231912" opacity="0.55">
        {[362, 392, 422, 452, 482].map((x) => <rect key={x} x={x} y="453" width="18" height="8" rx="2" />)}
      </g>
      {/* дверь */}
      <rect x="470" y="500" width="34" height="74" rx="2" fill="url(#ka-band)" />
      <rect x="476" y="506" width="22" height="62" rx="1" fill="#8a6a2e" opacity="0.6" />
      {/* Макам Ибрахим */}
      <rect x="612" y="566" width="10" height="26" rx="5" fill="#d8b865" />
      <circle cx="617" cy="562" r="6" fill="#d8b865" />

      <rect width="900" height="380" fill="url(#ka-fade)" />
    </svg>
  );
}
