/* ------------------------------------------------------------------ */
/*  ContextGauge — velocímetro semicircular (180°) de ventana de       */
/*  contexto. Se llena de izquierda a derecha con un degradé:          */
/*  verde → amarillo (todo amarillo al 55%) → rojo (todo rojo al 80%). */
/*  El centro muestra el porcentaje de context window usado.           */
/* ------------------------------------------------------------------ */

/** Interpola linealmente entre dos colores RGB. */
function lerpColor(
  from: [number, number, number],
  to: [number, number, number],
  t: number,
): string {
  const r = Math.round(from[0] + (to[0] - from[0]) * t);
  const g = Math.round(from[1] + (to[1] - from[1]) * t);
  const b = Math.round(from[2] + (to[2] - from[2]) * t);
  return `rgb(${r}, ${g}, ${b})`;
}

/** Color del arco según el porcentaje (0% verde, 55% amarillo, 80% rojo). */
function gaugeColor(percent: number): string {
  const p = Math.max(0, Math.min(100, percent));
  if (p <= 55) return lerpColor([34, 197, 94], [234, 179, 8], p / 55);
  if (p <= 80) return lerpColor([234, 179, 8], [239, 68, 68], (p - 55) / 25);
  return "rgb(239, 68, 68)";
}

/**
 * Velocímetro semicircular de ventana de contexto.
 *
 * @param percent - Porcentaje de context window usado (0-100).
 */
export function ContextGauge({ percent }: { percent: number }) {
  const clamped = Math.max(0, Math.min(100, percent));
  const color = gaugeColor(clamped);
  const R = 48;
  const cx = 60;
  const cy = 60;
  const circumference = Math.PI * R;
  const filled = (clamped / 100) * circumference;
  const dashoffset = circumference - filled;
  const path = `M ${cx - R} ${cy} A ${R} ${R} 0 0 1 ${cx + R} ${cy}`;

  return (
    <svg
      width="120"
      height="68"
      viewBox="0 0 120 68"
      className="shrink-0"
      role="img"
      aria-label={`Ventana de contexto: ${clamped.toFixed(2)}%`}
    >
      {/* Fondo (arco sin llenar) */}
      <path
        d={path}
        fill="none"
        stroke="#e5e7eb"
        strokeWidth="12"
        strokeLinecap="round"
      />
      {/* Arco lleno según porcentaje */}
      <path
        d={path}
        fill="none"
        stroke={color}
        strokeWidth="12"
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={dashoffset}
        style={{ transition: "stroke-dashoffset 0.4s ease, stroke 0.4s ease" }}
      />
      {/* Porcentaje en el centro */}
      <text
        x={cx}
        y={cy}
        textAnchor="middle"
        dominantBaseline="middle"
        fontSize="20"
        fontWeight="700"
        fill="#111827"
      >
{clamped.toFixed(2)}%
      </text>
    </svg>
  );
}

export default ContextGauge;