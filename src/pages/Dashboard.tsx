import { useCallback, useEffect, useState, type ReactNode } from 'react';
import type { Equipment, PageId } from '../types';
import { fetchDashboard, type DashboardSummary } from '../api/dashboard';
import { subscribeRealtime } from '../api/realtime';
import { EquipmentCard } from '../components/EquipmentCard';
import { StatusBadge } from '../components/StatusBadge';
import { badgeClass, buttonClass, cn, dotClass, ui } from '../utils/styles';

type StatCardProps = {
  label: string;
  value: ReactNode;
  unit?: string;
  sub: string;
  colorClass?: string;
  icon: string;
};

function StatCard({ label, value, unit, sub, colorClass, icon }: StatCardProps) {
  return (
    <div className={cn(ui.cardSm, 'flex flex-col gap-1.5')}>
      <div className="flex items-start justify-between">
        <span className="text-[11px] text-text-muted">{label}</span>
        <span className="text-base">{icon}</span>
      </div>
      <div className="flex items-baseline gap-1">
        <span className={cn('text-[28px] font-extrabold leading-none', colorClass ?? 'text-text-primary')}>{value}</span>
        {unit && <span className="text-xs text-text-muted">{unit}</span>}
      </div>
      {sub && <div className="text-[11px] text-text-muted">{sub}</div>}
    </div>
  );
}

function AlertBanner({ eq, onGo }: { eq: Equipment; onGo: (eq: Equipment) => void }) {
  return (
    <div className="flex items-center gap-3 rounded-md border border-red-500/25 bg-red-500/8 px-4 py-3">
      <span className="shrink-0 text-lg">🚨</span>
      <div className="flex-1">
        <div className="text-[13px] font-bold text-red-400">
          즉시 점검 필요 — {eq.name}
        </div>
        <div className="mt-0.5 text-xs text-text-secondary">
          잔여수명 <strong className="text-red-400">{eq.rul}h (±24h)</strong> ·
          {' '}고장 위험도 <strong className="text-red-400">{eq.risk}%</strong> ·
          {' '}AI 진단: {eq.faultType ?? '진단 대기'}
        </div>
      </div>
      <button className={buttonClass('danger', 'sm')} onClick={() => onGo(eq)}>
        상세 확인 →
      </button>
    </div>
  );
}

type Props = {
  onSelectEquipment: (eq: Equipment, page?: PageId) => void;
  onSummaryChange?: (summary: DashboardSummary) => void;
};

export function Dashboard({ onSelectEquipment, onSummaryChange }: Props) {
  const [selected, setSelected] = useState<number | null>(null);
  const [liveData, setLiveData] = useState<Equipment[]>([]);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadDashboard = useCallback((signal?: AbortSignal) => {
    return fetchDashboard(signal)
      .then(response => {
        setLiveData(response.data.equipment);
        setSummary(response.data.summary);
        onSummaryChange?.(response.data.summary);
        setLoadError(null);
      })
      .catch(error => {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return;
        }
        console.error('Failed to load dashboard data', error);
        setLoadError('백엔드 대시보드 API 연결 실패');
      })
      .finally(() => {
        if (!signal?.aborted) {
          setIsLoading(false);
        }
      });
  }, [onSummaryChange]);

  useEffect(() => {
    const controller = new AbortController();

    void loadDashboard(controller.signal);

    return () => controller.abort();
  }, [loadDashboard]);

  useEffect(() => {
    return subscribeRealtime(event => {
      setLiveData(event.dashboard.equipment);
      setSummary(event.dashboard.summary);
      onSummaryChange?.(event.dashboard.summary);
      setLoadError(null);
      setIsLoading(false);
    });
  }, [onSummaryChange]);

  const dangerEqs = liveData.filter(e => e.status === 'danger');
  const warnEqs   = liveData.filter(e => e.status === 'warn');
  const normalEqs = liveData.filter(e => e.status === 'normal');

  function handleSelect(eq: Equipment) {
    setSelected(eq.id);
    onSelectEquipment(eq);
  }

  if (isLoading) {
    return (
      <div className={cn(ui.card, 'px-5 py-4 text-sm text-text-secondary')}>
        대시보드 데이터를 불러오는 중입니다.
      </div>
    );
  }

  if (loadError || summary === null) {
    return (
      <div className="rounded-md border border-red-500/25 bg-red-500/8 px-4 py-3 text-sm text-red-300">
        {loadError ?? '대시보드 응답이 비어 있습니다.'}
      </div>
    );
  }

  return (
    <div className="flex animate-fade-in flex-col gap-5">
      <div className="grid grid-cols-4 gap-3">
        <StatCard label="총 설비"   value={summary.totalEquipment}   unit="대" sub={`가동 중 ${summary.totalEquipment}대`} colorClass="text-text-primary" icon="⚙" />
        <StatCard label="위험 설비" value={summary.dangerCount}      unit="대" sub="즉시 점검 필요"                         colorClass="text-red-400"      icon="🚨" />
        <StatCard label="경고 설비" value={summary.warnCount}        unit="대" sub="72h 내 예방 권장"                       colorClass="text-amber-400"    icon="⚠" />
        <StatCard label="월 가동률" value={summary.monthlyUptimePct} unit="%"  sub="목표 95% 초과"                          colorClass="text-green-400"    icon="📊" />
      </div>

      {dangerEqs.map(eq => (
        <AlertBanner key={eq.id} eq={eq} onGo={(e) => onSelectEquipment(e, 'detail')} />
      ))}

      <div>
        <div className="mb-3 flex items-center justify-between">
          <span className="text-[13px] font-semibold text-text-secondary">전체 설비 현황</span>
          <div className="flex items-center gap-2">
            <div className="flex gap-2">
              <span className={badgeClass('danger')}>
                <span className={dotClass('danger')} />위험 {dangerEqs.length}
              </span>
              <span className={badgeClass('warn')}>
                <span className={dotClass('warn')} />경고 {warnEqs.length}
              </span>
              <span className={badgeClass('normal')}>
                <span className={dotClass('normal')} />정상 {normalEqs.length}
              </span>
            </div>
          </div>
        </div>
        <div className="grid grid-cols-4 gap-3">
          {liveData.map(eq => (
            <EquipmentCard key={eq.id} eq={eq} selected={selected === eq.id} onClick={handleSelect} />
          ))}
        </div>
      </div>

      <div className={cn(ui.card, 'px-5 py-4')}>
        <div className={ui.sectionTitle}>
          실시간 센서 요약
        </div>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-xs">
            <thead>
              <tr className="border-b border-border">
                {['설비', '상태', '진동 (g)', '온도 (°C)', '전류 (A)', '유압 (bar)', 'RUL', '위험도'].map(h => (
                  <th key={h} className="px-2.5 py-1.5 text-left font-medium text-text-muted">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {liveData.map(eq => {
                const vColor = eq.sensors.vibration > 3 ? 'text-red-400' : eq.sensors.vibration > 2 ? 'text-amber-400' : 'text-text-primary';
                const tColor = eq.sensors.temp > 85 ? 'text-red-400' : eq.sensors.temp > 75 ? 'text-amber-400' : 'text-text-primary';
                const riskColor = eq.status === 'danger' ? 'bg-red-400' : eq.status === 'warn' ? 'bg-amber-400' : 'bg-green-400';
                const riskText = eq.status === 'danger' ? 'text-red-400' : eq.status === 'warn' ? 'text-amber-400' : 'text-green-400';
                const rulColor = eq.status === 'danger' ? 'text-red-400' : eq.status === 'warn' ? 'text-amber-400' : 'text-text-primary';
                return (
                  <tr
                    key={eq.id}
                    className="cursor-pointer border-b border-border transition-colors hover:bg-bg-card-hover"
                    onClick={() => handleSelect(eq)}
                  >
                    <td className="px-2.5 py-2 font-semibold">{eq.name}</td>
                    <td className="px-2.5 py-2"><StatusBadge status={eq.status} /></td>
                    <td className={cn('px-2.5 py-2 tabular-nums', vColor)}>{eq.sensors.vibration}</td>
                    <td className={cn('px-2.5 py-2 tabular-nums', tColor)}>{eq.sensors.temp}</td>
                    <td className="px-2.5 py-2 tabular-nums">{eq.sensors.current}</td>
                    <td className="px-2.5 py-2 tabular-nums">{eq.sensors.pressure}</td>
                    <td className={cn('px-2.5 py-2 font-semibold', rulColor)}>{eq.rul}h</td>
                    <td className="px-2.5 py-2">
                      <div className="flex items-center gap-1.5">
                        <div className="h-1 w-[50px] overflow-hidden rounded-[2px] bg-bg-base">
                          <div className={cn('h-full rounded-[2px]', riskColor)} style={{ width: `${eq.risk}%` }} />
                        </div>
                        <span className={cn('text-[11px] font-semibold', eq.status === 'normal' ? 'text-text-secondary' : riskText)}>{eq.risk}%</span>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
