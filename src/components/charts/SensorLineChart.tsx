import { useState } from 'react';
import type { SensorHistoryPoint } from '../../types';

type Props = {
  data: SensorHistoryPoint[];
  dataKey: 'vibration' | 'temperature' | 'current' | 'pressure';
  color: string;
  unit: string;
  label?: string;
  height?: number;
};

export function SensorLineChart({ data, dataKey, color, unit, height = 160 }: Props) {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  if (!data || data.length === 0) return null;

  const values = data.map(d => d[dataKey]);
  const min = Math.min(...values) * 0.95;
  const max = Math.max(...values) * 1.05;
  const w = 100, h = 100;
  const pts = values.map((v, i) => [
    (i / (values.length - 1)) * w,
    h - ((v - min) / (max - min)) * h,
  ] as const);
  const pathD = pts.map((p, i) => (i === 0 ? 'M' : 'L') + p[0].toFixed(2) + ',' + p[1].toFixed(2)).join(' ');
  const areaD = pathD + ' L' + pts[pts.length - 1][0] + ',' + h + ' L0,' + h + ' Z';
  const xLabels = data.filter((_, i) => i % Math.ceil(data.length / 6) === 0);

  return (
    <div className="relative w-full" style={{ height }}>
      <svg
        viewBox={`0 0 ${w} ${h}`}
        preserveAspectRatio="none"
        className="w-full"
        style={{ height: height - 20 }}
        onMouseMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          setHoverIdx(Math.min(data.length - 1, Math.round(((e.clientX - r.left) / r.width) * (data.length - 1))));
        }}
        onMouseLeave={() => setHoverIdx(null)}
      >
        <defs>
          <linearGradient id={'g-' + dataKey} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.3" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0, 25, 50, 75, 100].map(p => (
          <line key={p} x1="0" y1={(h * p) / 100} x2={w} y2={(h * p) / 100} stroke="#1e3050" strokeWidth="0.5" />
        ))}
        <path d={areaD} fill={`url(#g-${dataKey})`} />
        <path d={pathD} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        {hoverIdx !== null && (
          <>
            <line x1={pts[hoverIdx][0]} y1="0" x2={pts[hoverIdx][0]} y2={h} stroke={color} strokeWidth="0.8" strokeDasharray="2,2" opacity="0.6" />
            <circle cx={pts[hoverIdx][0]} cy={pts[hoverIdx][1]} r="2.5" fill={color} />
          </>
        )}
      </svg>
      <div className="mt-0.5 flex justify-between">
        {xLabels.map((d, i) => (
          <span key={i} className="text-[9px] text-text-muted">{d.time}</span>
        ))}
      </div>
      {hoverIdx !== null && (
        <div
          className="pointer-events-none absolute left-2 top-1 rounded-[5px] border border-border bg-bg-panel px-[7px] py-[3px] text-[11px]"
          style={{ color }}
        >
          {data[hoverIdx]?.time}: <strong>{values[hoverIdx]} {unit}</strong>
        </div>
      )}
    </div>
  );
}
