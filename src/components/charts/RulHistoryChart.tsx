import type { RulHistoryPoint } from '../../types';

type Props = { data: RulHistoryPoint[]; height?: number };

export function RulHistoryChart({ data, height = 200 }: Props) {
  if (!data || data.length === 0) return null;

  const values = data.map(d => d.rul);
  const uppers = data.map(d => d.upper);
  const lowers = data.map(d => d.lower);
  const allVals = [...values, ...uppers, ...lowers, 72];
  const min = Math.max(0, Math.min(...allVals) * 0.9);
  const max = Math.max(...allVals) * 1.05;
  const w = 100, h = 100;
  const toY = (v: number) => h - ((v - min) / (max - min)) * h;
  const toX = (i: number) => (i / (data.length - 1)) * w;

  const mainPath = values.map((v, i) => (i === 0 ? 'M' : 'L') + toX(i).toFixed(2) + ',' + toY(v).toFixed(2)).join(' ');
  const upperPath = uppers.map((v, i) => (i === 0 ? 'M' : 'L') + toX(i).toFixed(2) + ',' + toY(v).toFixed(2)).join(' ');
  const bandPath =
    upperPath + ' ' +
    lowers.map((_, i) => {
      const ri = lowers.length - 1 - i;
      return 'L' + toX(ri).toFixed(2) + ',' + toY(lowers[ri]).toFixed(2);
    }).join(' ') + ' Z';

  const alarmY = toY(72);
  const xLabels = data.filter((_, i) => i % Math.ceil(data.length / 6) === 0);

  return (
    <div className="w-full" style={{ height }}>
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="w-full" style={{ height: height - 20 }}>
        <defs>
          <linearGradient id="grad-rul" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#3b82f6" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0, 25, 50, 75, 100].map(p => (
          <line key={p} x1="0" y1={(h * p) / 100} x2={w} y2={(h * p) / 100} stroke="#1e3050" strokeWidth="0.5" />
        ))}
        <path d={bandPath} fill="rgba(59,130,246,0.08)" />
        <path d={mainPath + ' L' + toX(values.length - 1) + ',' + h + ' L0,' + h + ' Z'} fill="url(#grad-rul)" />
        <path d={mainPath} fill="none" stroke="#3b82f6" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        {alarmY >= 0 && alarmY <= h && (
          <line x1="0" y1={alarmY} x2={w} y2={alarmY} stroke="#ef4444" strokeWidth="0.8" strokeDasharray="2,2" />
        )}
      </svg>
      <div className="mt-0.5 flex justify-between">
        {xLabels.map((d, i) => (
          <span key={i} className="text-[9px] text-text-muted">{d.date}</span>
        ))}
      </div>
    </div>
  );
}
