import type { MonthlyStat } from '../../types';

type Props = { data: MonthlyStat[]; height?: number };

export function MonthlyDowntimeChart({ data, height = 200 }: Props) {
  if (!data || data.length === 0) return null;

  const maxDt = getNiceMax(Math.max(...data.map(d => d.downtime)));
  const maxPr = getNiceMax(Math.max(...data.map(d => d.prevented)));
  const groupW = 100 / data.length;
  const barW = Math.min(4.8, Math.max(2, groupW * 0.28));
  const pairGap = Math.min(1.2, Math.max(0.6, groupW * 0.08));
  const ticks = [1, 0.75, 0.5, 0.25, 0];
  const plotTop = 8;
  const plotBottom = 94;
  const plotHeight = plotBottom - plotTop;

  function getTickY(tick: number) {
    return plotTop + (1 - tick) * plotHeight;
  }

  return (
    <div className="grid w-full grid-cols-[34px_1fr_30px] grid-rows-[minmax(0,1fr)_18px] gap-x-2 overflow-hidden" style={{ height }}>
      <div className="relative text-[10px] text-blue-300/80">
        {ticks.map(tick => (
          <span
            key={tick}
            className="absolute right-0 -translate-y-1/2 tabular-nums"
            style={{ top: `${getTickY(tick)}%` }}
          >
            {formatTick(maxDt * tick)}
          </span>
        ))}
      </div>
      <div className="relative min-w-0 overflow-hidden">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="size-full">
          {ticks.map(tick => {
            const y = getTickY(tick);
            return <line key={tick} x1="0" y1={y} x2="100" y2={y} stroke="#1e3050" strokeWidth="0.5" />;
          })}
          {data.map((d, groupIndex) => {
            const center = groupIndex * groupW + groupW / 2;
            const downtimeHeight = (d.downtime / maxDt) * plotHeight;
            const preventedHeight = (d.prevented / maxPr) * plotHeight;
            return (
              <g key={d.month}>
                <rect
                  x={center - pairGap / 2 - barW}
                  y={plotBottom - downtimeHeight}
                  width={barW}
                  height={downtimeHeight}
                  fill="#3b82f6"
                  rx="0.8"
                />
                <rect
                  x={center + pairGap / 2}
                  y={plotBottom - preventedHeight}
                  width={barW}
                  height={preventedHeight}
                  fill="#4ade80"
                  rx="0.8"
                />
              </g>
            );
          })}
        </svg>
      </div>
      <div className="relative text-[10px] text-green-300/80">
        {ticks.map(tick => (
          <span
            key={tick}
            className="absolute left-0 -translate-y-1/2 tabular-nums"
            style={{ top: `${getTickY(tick)}%` }}
          >
            {formatTick(maxPr * tick)}
          </span>
        ))}
      </div>
      <div />
      <div className="grid min-w-0" style={{ gridTemplateColumns: `repeat(${data.length}, minmax(0, 1fr))` }}>
        {data.map(d => (
          <span key={d.month} className="self-end text-center text-[10px] text-text-muted">
            {d.month}
          </span>
        ))}
      </div>
      <div />
    </div>
  );
}

function getNiceMax(value: number) {
  if (value <= 0) return 1;

  const padded = value * 1.1;
  const magnitude = 10 ** Math.floor(Math.log10(padded));
  const normalized = padded / magnitude;
  const nice = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
  return nice * magnitude;
}

function formatTick(value: number) {
  return String(Math.round(value));
}
