import type { Equipment } from '../types';
import { StatusBadge } from './StatusBadge';
import { RiskBar } from './RiskBar';
import { cn } from '../utils/styles';

type Props = {
  eq: Equipment;
  onClick: (eq: Equipment) => void;
  selected?: boolean;
};

export function EquipmentCard({ eq, onClick, selected }: Props) {
  const isActive = !!selected;
  const statusBorder =
    eq.status === 'danger' ? 'border-red-400/40 shadow-[0_0_0_1px_rgba(248,113,113,0.2),0_4px_20px_rgba(248,113,113,0.1)]' :
    eq.status === 'warn'   ? 'border-amber-400/30' :
                              'border-border';
  const rulColor =
    eq.status === 'danger' ? 'text-red-400' :
    eq.status === 'warn'   ? 'text-amber-400' :
                              'text-text-primary';

  return (
    <div
      onClick={() => onClick(eq)}
      className={cn(
        'cursor-pointer rounded-md border p-4 transition-all duration-200',
        isActive ? 'border-blue-500 bg-bg-card-hover shadow-[0_0_0_2px_rgba(59,130,246,0.3)]' : cn('bg-bg-card', statusBorder),
      )}
    >
      <div className="mb-3 flex items-start justify-between">
        <div>
          <div className="mb-0.5 text-sm font-bold">{eq.name}</div>
          <div className="text-[11px] text-text-muted">{eq.model} · {eq.year}년식</div>
        </div>
        <StatusBadge status={eq.status} />
      </div>

      <div className="mb-3 flex items-baseline gap-1">
        <span className={cn('text-[28px] font-extrabold leading-none', rulColor)}>
          {eq.rul}
        </span>
        <span className="text-xs font-medium text-text-muted">h RUL</span>
        <span className="ml-0.5 text-[11px] text-text-muted">
          (±{Math.round((eq.rulMax - eq.rulMin) / 2)}h)
        </span>
      </div>

      <RiskBar value={eq.risk} status={eq.status} />

      <div className="mt-3 flex justify-between border-t border-border pt-2.5">
        <div>
          <div className="mb-0.5 text-[10px] text-text-muted">최근 정비</div>
          <div className="text-[11px] text-text-secondary">{eq.lastMaint}</div>
        </div>
        <div className="text-right">
          <div className="mb-0.5 text-[10px] text-text-muted">다음 예정</div>
          <div className={cn('text-[11px]', eq.status === 'danger' ? 'font-semibold text-red-400' : 'text-text-secondary')}>
            {eq.nextPlan}
          </div>
        </div>
      </div>

      {eq.faultType && (
        <div className="mt-2 flex items-center gap-1.5 rounded-sm bg-bg-base px-2.5 py-1.5">
          <span className="text-[10px] text-text-muted">AI 진단:</span>
          <span className={cn('text-[11px] font-semibold', eq.status === 'danger' ? 'text-red-400' : 'text-amber-400')}>
            {eq.faultType}
          </span>
          <span className="ml-auto text-[10px] text-text-muted">{eq.faultConf}%</span>
        </div>
      )}
    </div>
  );
}
