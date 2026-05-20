import type { FaultDistEntry } from '../../types';

type Props = { data: FaultDistEntry[]; height?: number };

export function FaultPieChart({ data, height = 200 }: Props) {
  if (!data || data.length === 0) return null;

  const total = data.reduce((s, d) => s + d.value, 0);
  const cx = 50, cy = 50, r = 35, ir = 22;
  const singleSlice = data.length === 1 || total === data[0]?.value;
  const slices = data.map((d, i) => {
    const startAngle = data
      .slice(0, i)
      .reduce((sum, entry) => sum + (entry.value / total) * Math.PI * 2, -Math.PI / 2);
    const sweep = (d.value / total) * Math.PI * 2;
    const angle = startAngle;
    const x1 = cx + r * Math.cos(angle), y1 = cy + r * Math.sin(angle);
    const x2 = cx + r * Math.cos(angle + sweep), y2 = cy + r * Math.sin(angle + sweep);
    const ix1 = cx + ir * Math.cos(angle), iy1 = cy + ir * Math.sin(angle);
    const ix2 = cx + ir * Math.cos(angle + sweep), iy2 = cy + ir * Math.sin(angle + sweep);
    const large = sweep > Math.PI ? 1 : 0;
    const path =
      `M${ix1.toFixed(2)},${iy1.toFixed(2)} ` +
      `L${x1.toFixed(2)},${y1.toFixed(2)} ` +
      `A${r},${r} 0 ${large} 1 ${x2.toFixed(2)},${y2.toFixed(2)} ` +
      `L${ix2.toFixed(2)},${iy2.toFixed(2)} ` +
      `A${ir},${ir} 0 ${large} 0 ${ix1.toFixed(2)},${iy1.toFixed(2)} Z`;
    return { ...d, path };
  });

  return (
    <div className="flex w-full items-center gap-3" style={{ height }}>
      <div className="h-full flex-[0_0_120px]">
        <svg viewBox="0 0 100 100" className="size-full">
          {singleSlice ? (
            <circle
              cx={cx}
              cy={cy}
              r={(r + ir) / 2}
              fill="none"
              stroke={data[0].color}
              strokeWidth={r - ir}
              opacity="0.9"
            />
          ) : (
            slices.map((s, i) => (
              <path key={i} d={s.path} fill={s.color} opacity="0.9" />
            ))
          )}
        </svg>
      </div>
      <div className="flex flex-1 flex-col gap-1.5">
        {data.map((d, i) => (
          <div key={i} className="flex items-center gap-2 text-xs">
            <span className="size-2.5 shrink-0 rounded-[2px]" style={{ background: d.color }} />
            <span className="flex-1 text-text-secondary">{d.name}</span>
            <span className="font-semibold text-text-primary">{d.value}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
