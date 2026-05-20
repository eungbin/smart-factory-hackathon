import type { EquipmentStatus } from '../types';
import { cn } from '../utils/styles';

export function RiskBar({ value, status }: { value: number; status: EquipmentStatus }) {
  const colorClass =
    status === 'danger' ? 'text-red-400' :
    status === 'warn'   ? 'text-amber-400' :
                          'text-green-400';
  const barClass =
    status === 'danger' ? 'bg-red-400' :
    status === 'warn'   ? 'bg-amber-400' :
                          'bg-green-400';
  return (
    <div className="w-full">
      <div className="mb-1 flex items-center justify-between">
        <span className="text-[11px] text-text-muted">고장 위험도</span>
        <span className={cn('text-[13px] font-bold', colorClass)}>{value}%</span>
      </div>
      <div className="h-1 overflow-hidden rounded-[2px] bg-bg-base">
        <div
          className={cn('h-full rounded-[2px] transition-[width] duration-500 ease-out', barClass)}
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  );
}
