import { useEffect, useState } from 'react';
import type { Equipment, PageId } from '../types';
import { buttonClass } from '../utils/styles';

type Props = {
  page: PageId;
  selectedEq: Equipment | null;
  onBack: () => void;
};

const TITLES: Record<PageId, { title: string; sub: string }> = {
  dashboard: { title: '메인 대시보드', sub: '실시간 설비 현황 모니터링' },
  detail:    { title: '설비 상세',     sub: 'RUL · 위험도 · 센서 트렌드' },
  workorder: { title: '작업지시서 생성', sub: 'AI 생성 정비 지시서 (LLM + RAG)' },
  workorders: { title: '작업지시서 관리', sub: '생성된 작업지시서 목록 · 상세 조회' },
  manuals:   { title: '메뉴얼 관리',   sub: 'RAG 출처 메뉴얼 조회' },
  result:    { title: '결과 입력',     sub: '정비 완료 결과 기록 · 학습 큐 적재' },
  report:    { title: '노하우 리포트', sub: '월간 정비 분석 · 데이터 자산화' },
};

function fmtTime(d: Date) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Seoul',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(d);
  const value = (type: string) => parts.find(part => part.type === type)?.value ?? '00';

  return `${value('year')}.${value('month')}.${value('day')} ${value('hour')}:${value('minute')}:${value('second')}`;
}

export function Header({ page, selectedEq, onBack }: Props) {
  const [time, setTime] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const base = TITLES[page];
  const title = page === 'detail' && selectedEq ? `${selectedEq.name} 상세 분석` : base.title;
  const sub = base.sub;

  return (
    <div className="flex pt-[13px] pb-[13px] shrink-0 items-center gap-3 border-b border-border bg-bg-panel px-6">
      {page !== 'dashboard' && (
        <button onClick={onBack} className={buttonClass('ghost', 'sm',)}>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M9 2L4 7L9 12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
      )}
      <div className="flex-1">
        <div className="text-[15px] font-bold">{title}</div>
        <div className="mt-px text-[11px] text-text-muted">{sub}</div>
      </div>

      <div className="flex items-center gap-1.5 rounded-sm border border-border bg-bg-card px-2.5 py-[5px]">
        <span className="size-1.5 rounded-full bg-green-400 shadow-[0_0_6px_var(--color-green-500)]" />
        <span className="text-[11px] text-text-secondary">센서 스트림 연결됨</span>
      </div>

      <div className="text-xs text-text-muted tabular-nums">
        {fmtTime(time)}
      </div>

      <div className="relative cursor-pointer p-1.5 text-text-secondary">
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
          <path d="M9 2a5 5 0 0 0-5 5v3l-1.5 2h13L14 10V7a5 5 0 0 0-5-5Z" stroke="currentColor" strokeWidth="1.5"/>
          <path d="M7 14a2 2 0 0 0 4 0" stroke="currentColor" strokeWidth="1.5"/>
        </svg>
        <span className="absolute right-0.5 top-0.5 size-2 rounded-full border-[1.5px] border-bg-panel bg-red-500" />
      </div>
    </div>
  );
}
