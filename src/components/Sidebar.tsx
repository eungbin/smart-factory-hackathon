import type { PageId } from '../types';
import { cn } from '../utils/styles';

type IconKey = 'grid' | 'chart' | 'doc' | 'check' | 'report';
type NavItem = { id: PageId; label: string; iconSvg: IconKey };

const NAV: NavItem[] = [
  { id: 'dashboard', label: '메인 대시보드', iconSvg: 'grid' },
  { id: 'detail',    label: '설비 상세',     iconSvg: 'chart' },
  { id: 'workorder', label: '작업지시서',    iconSvg: 'doc' },
  { id: 'result',    label: '결과 입력',     iconSvg: 'check' },
  { id: 'report',    label: '노하우 리포트', iconSvg: 'report' },
];

const ICONS: Record<IconKey, React.ReactElement> = {
  grid: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <rect x="1" y="1" width="6" height="6" rx="1.5" fill="currentColor" opacity="0.9"/>
      <rect x="9" y="1" width="6" height="6" rx="1.5" fill="currentColor" opacity="0.9"/>
      <rect x="1" y="9" width="6" height="6" rx="1.5" fill="currentColor" opacity="0.9"/>
      <rect x="9" y="9" width="6" height="6" rx="1.5" fill="currentColor" opacity="0.9"/>
    </svg>
  ),
  chart: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M2 12 L5 7 L8 9 L11 4 L14 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
      <line x1="2" y1="14" x2="14" y2="14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),
  doc: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <rect x="3" y="1" width="10" height="14" rx="2" stroke="currentColor" strokeWidth="1.5"/>
      <line x1="5.5" y1="5.5" x2="10.5" y2="5.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
      <line x1="5.5" y1="8" x2="10.5" y2="8" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
      <line x1="5.5" y1="10.5" x2="8.5" y2="10.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
    </svg>
  ),
  check: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <rect x="2" y="2" width="12" height="12" rx="2" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M5 8 L7 10 L11 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  report: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <rect x="2" y="1" width="12" height="14" rx="2" stroke="currentColor" strokeWidth="1.5"/>
      <rect x="4.5" y="7" width="2" height="5" rx="0.5" fill="currentColor"/>
      <rect x="7" y="5" width="2" height="7" rx="0.5" fill="currentColor"/>
      <rect x="9.5" y="9" width="2" height="3" rx="0.5" fill="currentColor"/>
    </svg>
  ),
};

type Props = {
  currentPage: PageId;
  onNavigate: (id: PageId) => void;
  alerts: number;
};

export function Sidebar({ currentPage, onNavigate, alerts }: Props) {
  return (
    <div className="flex h-full w-[220px] shrink-0 flex-col border-r border-border bg-bg-sidebar">
      <div className="border-b border-border px-5 pb-4 pt-5">
        <div className="flex items-center gap-2.5">
          <div className="flex size-[34px] shrink-0 items-center justify-center rounded bg-gradient-to-br from-blue-600 to-cyan-500 text-[15px]">⚙</div>
          <div>
            <div className="text-base font-extrabold leading-[1.1]">공장지기</div>
            <div className="mt-px text-[10px] text-text-muted">AI 정비지시 플랫폼</div>
          </div>
        </div>
      </div>

      <div className="border-b border-border px-5 py-3">
        <div className="mb-1 text-[10px] text-text-muted">현재 공장</div>
        <div className="text-xs font-semibold text-text-primary">시화공단 사출성형</div>
        <div className="text-[11px] text-text-muted">경기도 시흥시 · 설비 8대</div>
      </div>

      <nav className="flex flex-1 flex-col gap-0.5 p-3">
        {NAV.map(item => {
          const isActive = currentPage === item.id;
          const hasAlert = item.id === 'detail' && alerts > 0;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={cn(
                'relative flex w-full cursor-pointer items-center gap-2.5 rounded border-0 px-3 py-[9px] text-left font-sans text-[13px] transition-all duration-150 hover:bg-white/5 hover:text-text-primary',
                isActive ? 'bg-blue-500/15 font-semibold text-blue-400' : 'bg-transparent font-normal text-text-secondary',
              )}
            >
              <span className="size-4 shrink-0">{ICONS[item.iconSvg]}</span>
              <span>{item.label}</span>
              {hasAlert && (
                <span className="ml-auto flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">{alerts}</span>
              )}
            </button>
          );
        })}
      </nav>

      <div className="border-t border-border px-5 py-3.5">
        <div className="flex items-center gap-[9px]">
          <div className="flex size-[30px] shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-blue-700 to-cyan-600 text-xs font-bold">김</div>
          <div>
            <div className="text-xs font-semibold">김영수 반장</div>
            <div className="text-[10px] text-text-muted">생산팀장 · 관리자</div>
          </div>
        </div>
      </div>
    </div>
  );
}
