/**
 * Арабский геометрический орнамент «звезда и крест» для страницы входа.
 * Восьмиконечные звёзды (руб аль-хизб) с двойной линией — эффект переплетённых лент.
 */
export function StarPattern({ className = "" }: { className?: string }) {
  return (
    <svg className={className} aria-hidden="true">
      <defs>
        <pattern id="orn-star-cross" width="72" height="72" patternUnits="userSpaceOnUse">
          <g fill="none" stroke="#d2ad5e" strokeLinejoin="round">
            <polygon points="36.00,0.00 46.54,10.54 61.46,10.54 61.46,25.46 72.00,36.00 61.46,46.54 61.46,61.46 46.54,61.46 36.00,72.00 25.46,61.46 10.54,61.46 10.54,46.54 0.00,36.00 10.54,25.46 10.54,10.54 25.46,10.54" strokeWidth="1.1" />
            <polygon points="36.00,7.92 44.22,16.14 55.86,16.14 55.86,27.78 64.08,36.00 55.86,44.22 55.86,55.86 44.22,55.86 36.00,64.08 27.78,55.86 16.14,55.86 16.14,44.22 7.92,36.00 16.14,27.78 16.14,16.14 27.78,16.14" strokeWidth="0.6" strokeOpacity="0.7" />
            <polygon points="36.00,23.04 39.80,26.84 45.16,26.84 45.16,32.20 48.96,36.00 45.16,39.80 45.16,45.16 39.80,45.16 36.00,48.96 32.20,45.16 26.84,45.16 26.84,39.80 23.04,36.00 26.84,32.20 26.84,26.84 32.20,26.84" strokeWidth="0.8" strokeOpacity="0.8" />
            <g strokeWidth="0.7" strokeOpacity="0.7"><polygon points="0,-7 7,0 0,7 -7,0" /><polygon points="72,-7 79,0 72,7 65,0" /><polygon points="0,65 7,72 0,79 -7,72" /><polygon points="72,65 79,72 72,79 65,72" /></g>
          </g>
          <circle cx="36.0" cy="36.0" r="1.6" fill="#d2ad5e" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#orn-star-cross)" />
    </svg>
  );
}
