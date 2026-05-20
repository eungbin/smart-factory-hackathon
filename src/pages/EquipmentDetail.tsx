import { useEffect, useState } from 'react';
import type { Equipment, EquipmentStatus, MaintHistoryEntry, PageId, RulHistoryPoint, SensorHistoryPoint } from '../types';
import {
  fetchEquipmentList,
  fetchEquipmentMaintenanceHistory,
  fetchEquipmentRulHistory,
  fetchEquipmentSensorHistory,
} from '../api/equipment';
import { subscribeRealtime } from '../api/realtime';
import { StatusBadge } from '../components/StatusBadge';
import { SensorLineChart } from '../components/charts/SensorLineChart';
import { RulHistoryChart } from '../components/charts/RulHistoryChart';
import { badgeClass, buttonClass, cn, ui } from '../utils/styles';

type GaugeProps = {
  value: number;
  max?: number;
  color: string;
  size?: number;
  label: string;
  sublabel?: string;
};

function GaugeRing({ value, max = 100, color, size = 90, label, sublabel }: GaugeProps) {
  const r = size / 2 - 8;
  const circ = 2 * Math.PI * r;
  const pct = Math.min(value / max, 1);
  const dash = pct * circ;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--bg-base)" strokeWidth={7} />
        <circle
          cx={size / 2} cy={size / 2} r={r} fill="none"
          stroke={color} strokeWidth={7}
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: 'stroke-dasharray 0.8s ease', filter: `drop-shadow(0 0 6px ${color}88)` }}
        />
        <text
          x={size / 2} y={size / 2 - 4} textAnchor="middle"
          fill={color} fontSize={size > 80 ? 18 : 13} fontWeight={800} fontFamily="var(--font)"
        >{value}{max === 100 ? '%' : ''}</text>
        {sublabel && (
          <text x={size / 2} y={size / 2 + 14} textAnchor="middle" fill="var(--text-muted)" fontSize={9} fontFamily="var(--font)">
            {sublabel}
          </text>
        )}
      </svg>
      <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{label}</span>
    </div>
  );
}

type SensorRowProps = {
  label: string;
  value: number;
  unit: string;
  normal: number;
  warn: number;
  current: number;
  icon: string;
};

function SensorRow({ label, value, unit, normal, warn, current, icon }: SensorRowProps) {
  const pct = Math.min(current / (warn * 1.5), 1) * 100;
  const color = current >= warn ? 'var(--red-400)' : current >= normal ? 'var(--amber-400)' : 'var(--green-400)';
  return (
    <div style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 14 }}>{icon}</span>
          <span style={{ fontSize: 13, fontWeight: 600 }}>{label}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
          <span style={{
            fontSize: 20, fontWeight: 800, color,
            fontVariantNumeric: 'tabular-nums',
          }}>{value}</span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{unit}</span>
        </div>
      </div>
      <div style={{ height: 5, borderRadius: 3, background: 'var(--bg-base)', overflow: 'visible', position: 'relative' }}>
        <div style={{
          width: `${pct}%`, height: '100%', background: color,
          borderRadius: 3, transition: 'width 0.5s ease',
          boxShadow: `0 0 8px ${color}66`,
        }} />
        <div style={{ position: 'absolute', left: `${(normal / (warn * 1.5)) * 100}%`, top: -3, width: 1, height: 11, background: 'var(--amber-400)', opacity: 0.5 }} />
        <div style={{ position: 'absolute', left: `${(warn / (warn * 1.5)) * 100}%`, top: -3, width: 1, height: 11, background: 'var(--red-400)', opacity: 0.5 }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontSize: 10, color: 'var(--text-muted)' }}>
        <span>정상 &lt;{normal}{unit}</span>
        <span>경고 ≥{normal}{unit}</span>
        <span style={{ color: current >= warn ? 'var(--red-400)' : 'var(--text-muted)' }}>위험 ≥{warn}{unit}</span>
      </div>
    </div>
  );
}

type Props = {
  eq?: Equipment | null;
  onNavigate: (id: PageId, eq?: Equipment) => void;
  onChangeEquipment?: (eq: Equipment) => void;
};

type TabId = 'overview' | 'sensors' | 'rul' | 'history';
const TABS: { id: TabId; label: string }[] = [
  { id: 'overview', label: '개요' },
  { id: 'sensors',  label: '센서 트렌드' },
  { id: 'rul',      label: 'RUL 히스토리' },
  { id: 'history',  label: '정비 이력' },
];

const STATUS_META: Record<EquipmentStatus, { label: string; color: string; bg: string; border: string }> = {
  danger: {
    label: '위험',
    color: 'var(--color-red-400)',
    bg: 'rgba(248,113,113,0.14)',
    border: 'rgba(248,113,113,0.28)',
  },
  warn: {
    label: '경고',
    color: 'var(--color-amber-400)',
    bg: 'rgba(251,191,36,0.12)',
    border: 'rgba(251,191,36,0.26)',
  },
  normal: {
    label: '정상',
    color: 'var(--color-green-400)',
    bg: 'rgba(74,222,128,0.10)',
    border: 'rgba(74,222,128,0.22)',
  },
};

export function EquipmentDetail({ eq, onNavigate, onChangeEquipment }: Props) {
  const [equipmentList, setEquipmentList] = useState<Equipment[]>(eq ? [eq] : []);
  const [currentEq, setCurrentEq] = useState<Equipment | null>(eq ?? null);
  const [liveEq, setLiveEq] = useState<Equipment | null>(eq ?? null);
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const [isEquipmentMenuOpen, setEquipmentMenuOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [sensorHistory, setSensorHistory] = useState<SensorHistoryPoint[]>([]);
  const [rulHistory, setRulHistory] = useState<RulHistoryPoint[]>([]);
  const [maintenanceHistory, setMaintenanceHistory] = useState<MaintHistoryEntry[]>([]);

  function handleChangeEq(idStr: string) {
    const found = equipmentList.find(e => e.id === parseInt(idStr, 10));
    if (found) {
      setCurrentEq(found);
      setLiveEq(found);
      onChangeEquipment?.(found);
    }
  }

  useEffect(() => {
    const controller = new AbortController();

    fetchEquipmentList(controller.signal)
      .then(response => {
        const items = response.data;
        const preferred =
          (eq ? items.find(item => item.id === eq.id) : undefined) ??
          items.find(item => item.status === 'danger') ??
          items[0] ??
          null;

        setEquipmentList(items);
        setCurrentEq(preferred);
        setLiveEq(preferred);
        if (preferred && !eq) {
          onChangeEquipment?.(preferred);
        }
        setLoadError(null);
      })
      .catch(error => {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return;
        }
        console.error('Failed to load equipment list', error);
        setLoadError('백엔드 설비 API 연결 실패');
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      });

    return () => controller.abort();
  }, [eq, onChangeEquipment]);

  const currentEquipmentId = currentEq?.id;

  useEffect(() => {
    if (!currentEquipmentId) {
      return;
    }

    const controller = new AbortController();
    const equipmentId = currentEquipmentId;

    function loadHistories(signal?: AbortSignal) {
      return Promise.all([
        fetchEquipmentSensorHistory(equipmentId, signal),
        fetchEquipmentRulHistory(equipmentId, signal),
        fetchEquipmentMaintenanceHistory(equipmentId, signal),
      ]);
    }

    loadHistories(controller.signal)
      .then(([sensorResponse, rulResponse, maintenanceResponse]) => {
        setSensorHistory(sensorResponse.data);
        setRulHistory(rulResponse.data);
        setMaintenanceHistory(maintenanceResponse.data);
      })
      .catch(error => {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return;
        }
        console.error('Failed to load equipment history', error);
      });

    const unsubscribe = subscribeRealtime(event => {
      const items = event.dashboard.equipment;
      const selected = items.find(item => item.id === equipmentId) ?? null;

      setEquipmentList(items);
      if (selected) {
        setCurrentEq(selected);
        setLiveEq(selected);
        onChangeEquipment?.(selected);
      }

      loadHistories()
        .then(([sensorResponse, rulResponse, maintenanceResponse]) => {
          setSensorHistory(sensorResponse.data);
          setRulHistory(rulResponse.data);
          setMaintenanceHistory(maintenanceResponse.data);
        })
        .catch(error => {
          console.error('Failed to refresh equipment history', error);
        });
    });

    return () => {
      controller.abort();
      unsubscribe();
    };
  }, [currentEquipmentId, onChangeEquipment]);

  if (isLoading) {
    return (
      <div className={cn(ui.card, 'px-5 py-4 text-sm text-text-secondary')}>
        설비 상세 데이터를 불러오는 중입니다.
      </div>
    );
  }

  if (loadError || !currentEq || !liveEq) {
    return (
      <div className="rounded-md border border-red-500/25 bg-red-500/8 px-4 py-3 text-sm text-red-300">
        {loadError ?? '설비 상세 응답이 비어 있습니다.'}
      </div>
    );
  }

  const riskColor = liveEq.status === 'danger' ? 'var(--color-red-400)' : liveEq.status === 'warn' ? 'var(--color-amber-400)' : 'var(--color-green-400)';
  const currentMeta = STATUS_META[currentEq.status];

  return (
    <div className="flex animate-fade-in flex-col gap-4">
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '10px 16px', background: 'var(--color-bg-panel)',
        border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)',
      }}>
        <span style={{ fontSize: 12, color: 'var(--color-text-muted)', flexShrink: 0 }}>설비 선택</span>
        <div
          style={{ position: 'relative', flex: '0 0 200px' }}
          onBlur={(event) => {
            const nextFocus = event.relatedTarget;
            if (!(nextFocus instanceof Node) || !event.currentTarget.contains(nextFocus)) {
              setEquipmentMenuOpen(false);
            }
          }}
        >
          <button
            type="button"
            aria-haspopup="listbox"
            aria-expanded={isEquipmentMenuOpen}
            onClick={() => setEquipmentMenuOpen(open => !open)}
            style={{
              width: '100%',
              background: 'var(--color-bg-card)',
              border: '1px solid var(--color-border-lite)',
              borderRadius: 8, color: 'var(--color-text-primary)', fontFamily: 'var(--font-sans)',
              fontSize: 13, fontWeight: 700, padding: '8px 36px 8px 12px',
              cursor: 'pointer', outline: 'none',
              display: 'flex', alignItems: 'center', gap: 7, textAlign: 'left',
            }}
          >
            <span style={{ width: 7, height: 7, borderRadius: '50%', background: currentMeta.color, boxShadow: `0 0 6px ${currentMeta.color}`, flexShrink: 0 }} />
            <span style={{ flex: 1 }}>{currentEq.name}</span>
            <span style={{ color: currentMeta.color, fontSize: 11 }}>{currentMeta.label}</span>
          </button>
          <svg
            style={{ position: 'absolute', right: 9, top: 10, pointerEvents: 'none', width: 18, height: 18, padding: 4, borderRadius: 5, background: 'var(--color-bg-base)', border: '1px solid var(--color-border)' }}
            width="22" height="22" viewBox="0 0 12 12" fill="none"
          >
            <path d="M2 4L6 8L10 4" stroke="var(--color-text-secondary)" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          {isEquipmentMenuOpen && (
            <div
              role="listbox"
              aria-label="설비 선택"
              style={{
                position: 'absolute', top: 'calc(100% + 6px)', left: 0, right: 0, zIndex: 20,
                display: 'flex', flexDirection: 'column', gap: 4, padding: 6,
                background: 'var(--color-bg-panel)', border: '1px solid var(--color-border-lite)',
                borderRadius: 8, boxShadow: '0 16px 36px rgba(0,0,0,0.35)',
              }}
            >
              {equipmentList.map(e => {
                const meta = STATUS_META[e.status];
                const isSelected = e.id === currentEq.id;
                return (
                  <button
                    key={e.id}
                    type="button"
                    role="option"
                    aria-selected={isSelected}
                    onClick={() => {
                      handleChangeEq(String(e.id));
                      setEquipmentMenuOpen(false);
                    }}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 8,
                      width: '100%', padding: '7px 8px', borderRadius: 6,
                      border: `1px solid ${isSelected ? 'var(--color-border-lite)' : 'transparent'}`,
                      background: isSelected ? 'rgba(255,255,255,0.05)' : 'transparent',
                      color: 'var(--color-text-primary)', fontFamily: 'var(--font-sans)',
                      fontSize: 12, fontWeight: 700, cursor: 'pointer', textAlign: 'left',
                    }}
                  >
                    <span style={{ width: 7, height: 7, borderRadius: '50%', background: meta.color, boxShadow: `0 0 6px ${meta.color}`, flexShrink: 0 }} />
                    <span style={{ flex: 1 }}>{e.name}</span>
                    <span style={{ color: meta.color, fontSize: 11 }}>{meta.label}</span>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', gap: 6, flex: 1 }}>
          {equipmentList.filter(e => e.status !== 'normal').map(e => {
            const isActive = e.id === currentEq.id;
            const meta = STATUS_META[e.status];
            return (
              <button
                key={e.id}
                onClick={() => handleChangeEq(String(e.id))}
                style={{
                  padding: '5px 11px', borderRadius: 6,
                  border: `1px solid ${isActive ? meta.border : 'var(--color-border)'}`,
                  background: isActive ? meta.bg : 'rgba(255,255,255,0.03)',
                  color: isActive ? meta.color : 'var(--color-text-secondary)',
                  fontFamily: 'var(--font-sans)', fontSize: 11, fontWeight: 700,
                  cursor: 'pointer', transition: 'all 0.15s',
                  display: 'flex', alignItems: 'center', gap: 5,
                }}
              >
                <span style={{
                  width: 7, height: 7, borderRadius: '50%',
                  background: meta.color, flexShrink: 0, boxShadow: `0 0 6px ${meta.color}`,
                }} />
                {e.name}
              </button>
            );
          })}
        </div>

        <div style={{ display: 'flex', gap: 10, flexShrink: 0 }}>
          {(['danger', 'warn', 'normal'] as const).map(status => {
            const meta = STATUS_META[status];
            return (
              <div key={status} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '4px 9px', borderRadius: 999, border: `1px solid ${meta.border}`, background: meta.bg, fontSize: 11, fontWeight: 700, color: meta.color }}>
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: meta.color, boxShadow: `0 0 6px ${meta.color}` }} />
                <span>{meta.label}</span>
                <span>{equipmentList.filter(e => e.status === status).length}</span>
              </div>
            );
          })}
        </div>
      </div>

      <div className={ui.card} style={{ background: 'linear-gradient(135deg, var(--bg-card) 0%, rgba(13,23,41,0.95) 100%)' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 20, flexWrap: 'wrap' }}>
          <div style={{ flex: '0 0 220px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <div style={{
                width: 42, height: 42, borderRadius: 10,
                background: liveEq.status === 'danger' ? 'rgba(239,68,68,0.15)' :
                           liveEq.status === 'warn'   ? 'rgba(245,158,11,0.15)' :
                                                        'rgba(59,130,246,0.15)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20,
              }}>⚙</div>
              <div>
                <div style={{ fontWeight: 800, fontSize: 17 }}>{liveEq.name}</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{liveEq.model} · {liveEq.year}년식</div>
              </div>
              <StatusBadge status={liveEq.status} />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 11 }}>
              {([
                ['최근 정비', liveEq.lastMaint],
                ['다음 예정', liveEq.nextPlan],
                ['누적 가동', '42,180h'],
                ['담당자', '박영수 (정비)'],
              ] as const).map(([k, v]) => (
                <div key={k}>
                  <div style={{ color: 'var(--text-muted)', marginBottom: 2 }}>{k}</div>
                  <div style={{
                    color: liveEq.status === 'danger' && k === '다음 예정' ? 'var(--red-400)' : 'var(--text-secondary)',
                    fontWeight: 500,
                  }}>{v}</div>
                </div>
              ))}
            </div>
          </div>

          <div style={{ width: 1, background: 'var(--border)', alignSelf: 'stretch' }} />

          <div style={{ flex: '0 0 280px' }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--blue-400)', display: 'inline-block' }} />
              AI #1 — 추정 모듈 출력
            </div>
            <div style={{ display: 'flex', gap: 20, alignItems: 'center' }}>
              <GaugeRing value={liveEq.risk} max={100} color={riskColor} size={100} label="고장 위험도" sublabel="%" />
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>잔여 가동 시간 (RUL)</div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
                  <span style={{ fontSize: 38, fontWeight: 900, color: riskColor, lineHeight: 1 }}>{liveEq.rul}</span>
                  <span style={{ fontSize: 14, color: 'var(--text-muted)' }}>h</span>
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                  신뢰구간 {liveEq.rulMin}h ~ {liveEq.rulMax}h
                </div>
                {(liveEq.faultType || liveEq.status !== 'normal') && (
                  <div style={{
                    marginTop: 8, padding: '5px 10px',
                    background: 'rgba(239,68,68,0.08)',
                    border: '1px solid rgba(239,68,68,0.2)',
                    borderRadius: 6, fontSize: 12,
                  }}>
                    <span style={{ color: 'var(--text-muted)' }}>AI 진단: </span>
                    <span style={{ color: riskColor, fontWeight: 700 }}>
                      {liveEq.faultType ?? '진단 대기'} {liveEq.faultConf !== null ? `${liveEq.faultConf}%` : ''}
                    </span>
                  </div>
                )}
                {liveEq.faultTop3.length > 0 && (
                  <div style={{
                    marginTop: 8,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 4,
                    fontSize: 11,
                  }}>
                    <div style={{ color: 'var(--text-muted)' }}>AI 진단 후보</div>
                    {liveEq.faultTop3.map((candidate, index) => (
                      <div
                        key={candidate.faultTypeCode}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 8,
                          padding: '4px 8px',
                          borderRadius: 5,
                          background: 'var(--bg-base)',
                        }}
                      >
                        <span style={{ color: 'var(--text-muted)', width: 12 }}>{index + 1}</span>
                        <span style={{ flex: 1, color: 'var(--text-secondary)' }}>{candidate.faultType}</span>
                        <span style={{ fontWeight: 700, color: riskColor }}>{candidate.probability}%</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          <div style={{ width: 1, background: 'var(--border)', alignSelf: 'stretch' }} />

          <div style={{ flex: 1, minWidth: 180 }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 10 }}>
              근거 센서 (Feature Importance)
            </div>
            {[
              { label: '진동 RMS',         delta: '+31%', color: 'var(--red-400)',   pct: 85 },
              { label: '모터 전류 변동성', delta: '+18%', color: 'var(--amber-400)', pct: 62 },
              { label: '유압 온도',        delta: '+12%', color: 'var(--amber-400)', pct: 48 },
            ].map((s, i) => (
              <div key={i} style={{ marginBottom: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                  <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{s.label}</span>
                  <span style={{ fontSize: 11, fontWeight: 700, color: s.color }}>{s.delta}</span>
                </div>
                <div style={{ height: 4, background: 'var(--bg-base)', borderRadius: 2 }}>
                  <div style={{
                    width: `${s.pct}%`, height: '100%',
                    background: s.color, borderRadius: 2,
                    transition: 'width 0.8s ease',
                  }} />
                </div>
              </div>
            ))}
            <div style={{ marginTop: 12 }}>
              <button className={cn(buttonClass('primary'), 'w-full')} onClick={() => onNavigate('workorder', liveEq)}>
                작업지시서 생성 →
              </button>
            </div>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--color-border)' }}>
        {TABS.map(t => (
          <button
            key={t.id}
            type="button"
            onClick={() => setActiveTab(t.id)}
            style={{
              padding: '8px 18px', border: 0, background: 'transparent',
              color: activeTab === t.id ? 'var(--color-blue-400)' : 'var(--color-text-muted)',
              fontFamily: 'var(--font-sans)', fontSize: 13,
              fontWeight: activeTab === t.id ? 600 : 400,
              cursor: 'pointer',
              borderBottom: `2px solid ${activeTab === t.id ? 'var(--color-blue-400)' : 'transparent'}`,
              marginBottom: -1, transition: 'color 0.15s, border-color 0.15s',
            }}
          >{t.label}</button>
        ))}
      </div>

      {activeTab === 'overview' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
          <div className={ui.card}>
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 14, color: 'var(--text-secondary)' }}>실시간 센서값</div>
            <SensorRow label="진동 (RMS)" value={liveEq.sensors.vibration} unit="g"   normal={1.5} warn={3.0} current={liveEq.sensors.vibration} icon="📳" />
            <SensorRow label="온도"        value={liveEq.sensors.temp}      unit="°C"  normal={75}  warn={88}  current={liveEq.sensors.temp}      icon="🌡" />
            <SensorRow label="모터 전류"   value={liveEq.sensors.current}   unit="A"   normal={25}  warn={30}  current={liveEq.sensors.current}   icon="⚡" />
            <SensorRow label="유압 압력"   value={liveEq.sensors.pressure}  unit="bar" normal={150} warn={160} current={liveEq.sensors.pressure}  icon="💧" />
          </div>
          <div className={ui.card}>
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 14, color: 'var(--text-secondary)' }}>설비 스펙 & 알람 임계값</div>
            {([
              ['모델', liveEq.model],
              ['제조연도', `${liveEq.year}년`],
              ['설비 나이', `${2026 - liveEq.year}년`],
              ['진동 경보 기준', '진동 ≥1.5g / 위험 ≥3.0g'],
              ['온도 경보 기준', '≥75°C / 위험 ≥88°C'],
              ['전류 경보 기준', '≥25A / 위험 ≥30A'],
              ['AI 모델', 'LSTM + 1D-CNN (C-MAPSS/AI Hub)'],
            ] as const).map(([k, v]) => (
              <div key={k} style={{
                display: 'flex', justifyContent: 'space-between',
                padding: '7px 0', borderBottom: '1px solid var(--border)',
                fontSize: 12,
              }}>
                <span style={{ color: 'var(--text-muted)' }}>{k}</span>
                <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{v}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'sensors' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
          {([
            { dataKey: 'vibration',   color: '#f87171', unit: 'g',   title: '진동 (RMS)' },
            { dataKey: 'temperature', color: '#fbbf24', unit: '°C',  title: '유압 온도' },
            { dataKey: 'current',     color: '#60a5fa', unit: 'A',   title: '모터 전류' },
            { dataKey: 'pressure',    color: '#34d399', unit: 'bar', title: '유압 압력' },
          ] as const).map(cfg => (
            <div key={cfg.dataKey} className={ui.card}>
              <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 10, color: 'var(--text-secondary)' }}>
                {cfg.title} — 최근 24h
              </div>
              <SensorLineChart data={sensorHistory} dataKey={cfg.dataKey} color={cfg.color} unit={cfg.unit} height={150} />
            </div>
          ))}
          <div className={ui.card}>
            <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 8, color: 'var(--text-secondary)' }}>센서 이상 시각</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
              {([
                { time: '03:00', sensor: '진동 RMS', value: '3.8g',  level: 'danger' },
                { time: '05:30', sensor: '유압 온도', value: '89°C',  level: 'danger' },
                { time: '07:00', sensor: '모터 전류', value: '28.4A', level: 'warn' },
                { time: '08:10', sensor: '진동 RMS', value: '4.1g',  level: 'danger' },
              ] as const).map((ev, i) => (
                <div key={i} style={{
                  display: 'flex', gap: 10, padding: '8px 10px',
                  background: 'var(--bg-base)', borderRadius: 6, alignItems: 'center',
                }}>
                  <span style={{ color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums', width: 36 }}>{ev.time}</span>
                  <span className={cn(badgeClass(ev.level), 'px-1.5 py-px')}>
                    {ev.level === 'danger' ? '위험' : '경고'}
                  </span>
                  <span style={{ color: 'var(--text-secondary)' }}>{ev.sensor}</span>
                  <span style={{
                    marginLeft: 'auto', fontWeight: 700,
                    color: ev.level === 'danger' ? 'var(--red-400)' : 'var(--amber-400)',
                  }}>{ev.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'rul' && (
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16 }}>
          <div className={ui.card}>
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 12, color: 'var(--text-secondary)' }}>RUL 추이 — 최근 30일</div>
            <RulHistoryChart data={rulHistory} height={240} />
            <div style={{ marginTop: 10, fontSize: 11, color: 'var(--text-muted)', display: 'flex', gap: 16 }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 20, height: 2, background: '#3b82f6', display: 'inline-block' }} />예측 RUL
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 20, height: 2, background: 'rgba(59,130,246,0.3)', display: 'inline-block' }} />신뢰 구간
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 14, height: 1, background: '#ef4444', borderTop: '2px dashed #ef4444', display: 'inline-block' }} />임계값
              </span>
            </div>
          </div>
          <div className={ui.card}>
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 12, color: 'var(--text-secondary)' }}>AI 모델 성능</div>
            {([
              { label: 'RMSE',           value: '14.2 cycles', good: true },
              { label: 'PHM Score',      value: '0.83',         good: true },
              { label: '고장 미탐률',    value: '7.4%',         good: true },
              { label: '불필요 정비율',  value: '11.2%',        good: true },
              { label: '학습 데이터',    value: 'C-MAPSS FD001' },
              { label: '도메인 보강',    value: 'AI Hub #238' },
            ] as { label: string; value: string; good?: boolean }[]).map(m => (
              <div key={m.label} style={{
                display: 'flex', justifyContent: 'space-between',
                padding: '8px 0', borderBottom: '1px solid var(--border)',
                fontSize: 12,
              }}>
                <span style={{ color: 'var(--text-muted)' }}>{m.label}</span>
                <span style={{
                  color: m.good === true ? 'var(--green-400)' :
                         m.good === false ? 'var(--red-400)' :
                                            'var(--text-primary)',
                  fontWeight: 600,
                }}>{m.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'history' && (
        <div className={ui.card}>
          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 14, color: 'var(--text-secondary)' }}>정비 이력</div>
          {maintenanceHistory.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', fontSize: 13, textAlign: 'center', padding: 24 }}>
              정비 이력이 없습니다.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {maintenanceHistory.map(h => (
                <div key={h.id} style={{
                  padding: '12px 14px', background: 'var(--bg-base)',
                  borderRadius: 8, border: '1px solid var(--border)',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      <span className={badgeClass(h.type === '긴급 정비' ? 'danger' : 'info')}>{h.type}</span>
                      <span style={{ fontSize: 13, fontWeight: 600 }}>{h.date}</span>
                    </div>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>소요 {h.duration}분 · {h.tech}</span>
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                    <span style={{ color: 'var(--text-muted)' }}>교체 부품: </span>{h.parts}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>{h.note}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
