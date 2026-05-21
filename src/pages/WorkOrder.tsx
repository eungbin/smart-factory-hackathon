import { useState } from 'react';
import type { Equipment, WorkOrder as WorkOrderT, WorkOrderSourceRef, WorkOrderStep } from '../types';
import { generateWorkOrder } from '../api/workOrders';
import { badgeClass, buttonClass, cn, ui } from '../utils/styles';

type Status = 'idle' | 'loading' | 'done';

const LOADING_STEPS: [number, string][] = [
  [300,  'RAG 지식베이스 검색 중 (설비 매뉴얼 §4.3)...'],
  [700,  'C-MAPSS 추정 결과 통합 중 (RUL 72h ±24h)...'],
  [1200, 'AI Hub 고장 분류 결과 병합 (베어링 불량 78%)...'],
  [1800, 'Gemini API 호출 → 작업지시서 초안 생성 중...'],
  [2600, '매뉴얼 출처 매핑 및 체크리스트 검증 중...'],
  [3200, '안전수칙 및 소모품 목록 확정 중...'],
  [3800, '지시서 완성 — 검토 대기 중'],
];

const STEP_CAT_CLASS: Record<WorkOrderStep['category'], { text: string; border: string; bg: string }> = {
  '안전': { text: 'text-red-400',       border: 'border-red-400',       bg: 'bg-red-400/12' },
  '진단': { text: 'text-blue-400',      border: 'border-blue-400',      bg: 'bg-blue-400/12' },
  '윤활': { text: 'text-cyan-400',      border: 'border-cyan-400',      bg: 'bg-cyan-400/12' },
  '부품': { text: 'text-amber-400',     border: 'border-amber-400',     bg: 'bg-amber-400/12' },
  '복구': { text: 'text-green-400',     border: 'border-green-400',     bg: 'bg-green-400/12' },
  '기록': { text: 'text-text-secondary', border: 'border-text-secondary', bg: 'bg-white/5' },
};

type Props = {
  eq: Equipment;
  onSendKakao: (order: WorkOrderT) => void;
  onOpenManual: (sourceRef: WorkOrderSourceRef) => void;
  onGenerated: (order: WorkOrderT & { id: number }) => void;
  onNavigateResult: () => void;
};

export function WorkOrder({ eq, onSendKakao, onOpenManual, onGenerated, onNavigateResult }: Props) {
  const [status, setStatus] = useState<Status>('idle');
  const [progress, setProgress] = useState(0);
  const [progressMsg, setProgressMsg] = useState('');
  const [order, setOrder] = useState<WorkOrderT | null>(null);
  const [approved, setApproved] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const targetEq = eq;

  function handleGenerate() {
    setStatus('loading');
    setProgress(0);
    setLoadError(null);
    let i = 0;
    function next() {
      if (i >= LOADING_STEPS.length) {
        generateWorkOrder(targetEq.id)
          .then(response => {
            setOrder(response.data);
            setStatus('done');
            onGenerated(response.data);
          })
          .catch(error => {
            console.error('Failed to generate work order', error);
            setLoadError('작업지시서 API 연결에 실패했습니다.');
            setStatus('idle');
          });
        return;
      }
      const [, msg] = LOADING_STEPS[i];
      setTimeout(() => {
        setProgressMsg(msg);
        setProgress(Math.round(((i + 1) / LOADING_STEPS.length) * 100));
        i++;
        next();
      }, i === 0 ? 0 : LOADING_STEPS[i - 1][0]);
    }
    next();
  }

  return (
    <div className="flex animate-fade-in flex-col gap-4">
      <div className={cn(ui.card, 'flex flex-wrap items-center justify-between gap-3')}>
        <div>
          <div className="text-base font-bold">작업지시서 생성</div>
          <div className="mt-0.5 text-xs text-text-muted">
            대상: <strong className="text-text-primary">{targetEq.name}</strong>
            {' '}· AI #2 (Gemini API + RAG) 기반 자동 생성
          </div>
        </div>
        {status === 'idle' && (
          <button className={buttonClass('primary', 'lg')} onClick={handleGenerate}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M8 2L9.5 6.5H14L10.5 9L11.5 13.5L8 11L4.5 13.5L5.5 9L2 6.5H6.5L8 2Z" fill="currentColor" />
            </svg>
            AI 작업지시서 생성
          </button>
        )}
        {status === 'done' && !approved && (
          <div className="flex gap-2">
            <button className={buttonClass('secondary')} onClick={() => { setStatus('idle'); setOrder(null); }}>재생성</button>
            <button className={buttonClass('primary', 'lg')} onClick={() => setApproved(true)}>
              ✓ 승인 후 전송
            </button>
          </div>
        )}
        {approved && order && (
          <button
            className={cn(ui.button.base, ui.button.lg, 'border-green-400/30 bg-green-500/20 text-green-400 hover:bg-green-500/25')}
            onClick={() => onSendKakao(order)}
          >
            📱 카카오톡으로 전송
          </button>
        )}
      </div>

      {loadError && (
        <div className="rounded-md border border-red-500/25 bg-red-500/8 px-4 py-3 text-sm text-red-300">
          {loadError}
        </div>
      )}

      {status === 'loading' && (
        <div className={cn(ui.card, 'animate-fade-in p-8 text-center')}>
          <div className="mb-5">
            <svg className="mx-auto block animate-spin-fast" width="36" height="36" viewBox="0 0 36 36" fill="none">
              <circle cx="18" cy="18" r="15" stroke="var(--border)" strokeWidth="3" />
              <path d="M18 3 A15 15 0 0 1 33 18" stroke="var(--blue-400)" strokeWidth="3" strokeLinecap="round" />
            </svg>
          </div>
          <div className="mb-2 text-sm font-semibold">Gemini API 처리 중...</div>
          <div className="mb-4 min-h-5 text-xs italic text-blue-400">
            {progressMsg}
          </div>
          <div className="mx-auto h-1.5 w-3/5 rounded-[3px] bg-bg-base">
            <div
              className="h-full rounded-[3px] bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.5)] transition-[width] duration-[400ms] ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="mt-2 text-[11px] text-text-muted">{progress}%</div>
        </div>
      )}

      {status === 'done' && order && (
        <div className="flex animate-fade-in flex-col gap-3.5">
          <div className={cn(ui.cardSm, 'border-blue-500/20 bg-blue-500/6')}>
            <div className="flex flex-wrap gap-4 text-xs">
              {([
                ['설비',     order.equipName],
                ['생성시각', order.generatedAt],
                ['RUL',      order.rul],
                ['위험도',   `${order.risk}%`],
                ['AI 진단',  order.faultType],
                ['출처',     order.source],
              ] as const).map(([k, v]) => (
                <div key={k}>
                  <span className="text-text-muted">{k}: </span>
                  <span
                    className={cn(
                      'font-semibold',
                      k === '위험도' || k === 'AI 진단' ? 'text-red-400' : k === '출처' ? 'text-blue-300' : 'text-text-primary',
                    )}
                  >{v}</span>
                </div>
              ))}
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {order.rootSensors.map((s, i) => <span key={i} className={ui.tag}>{s}</span>)}
            </div>
          </div>

          <div className={ui.card}>
            <div className="mb-3.5 flex items-center justify-between">
              <div className="text-[13px] font-semibold text-text-secondary">
                작업 절차 ({order.steps.length}단계)
              </div>
              <div className="text-xs text-text-muted">
                총 소요시간: <strong className="text-text-primary">{order.totalTime}</strong> · {order.techLevel}
              </div>
            </div>
            <div className="flex flex-col gap-2">
              {order.steps.map((step, i) => {
                const cat = STEP_CAT_CLASS[step.category];
                return (
                <div
                  key={i}
                  className={cn(
                    'flex items-start gap-3 rounded border bg-bg-base px-3.5 py-3',
                    step.safety ? 'border-red-400/25' : 'border-border',
                  )}
                >
                  <div className={cn('flex size-[26px] shrink-0 items-center justify-center rounded-full border-2 bg-bg-card text-[11px] font-bold', cat.border, cat.text)}>{step.no}</div>
                  <div className="flex-1">
                    <div className="mb-1 flex items-center gap-1.5">
                      <span className={cn('rounded-[3px] px-1.5 py-px text-[10px] font-bold', cat.bg, cat.text)}>{step.category}</span>
                      {step.safety && <span className="text-[10px] font-semibold text-red-400">⚠ 안전 필수</span>}
                      <span className="ml-auto text-[11px] text-text-muted">{step.time}</span>
                    </div>
                    <div className="text-[13px] leading-normal text-text-primary">{step.action}</div>
                    <div className="mt-1 text-[11px] text-text-muted">도구: {step.tool}</div>
                  </div>
                </div>
                );
              })}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3.5">
            <div className={ui.card}>
              <div className={ui.sectionTitle}>
                필요 소모품 / 부품
              </div>
              {order.parts.map((p, i) => (
                <div key={i} className="flex items-center justify-between border-b border-border py-[7px] text-xs">
                  <span className="text-text-primary">{p.name}</span>
                  <div className="flex gap-2">
                    <span className="text-text-muted">{p.qty}</span>
                    <span
                      className={cn(badgeClass(p.stock === '보유중' || p.stock.includes('재고') ? 'normal' : 'warn'), 'text-[10px]')}
                    >{p.stock}</span>
                  </div>
                </div>
              ))}
            </div>
            <div className={cn(ui.card, 'border-red-400/15 bg-red-400/5')}>
              <div className="mb-2.5 text-[13px] font-semibold text-red-400">⚠ 안전 주의사항</div>
              <p className="text-xs leading-[1.7] text-text-secondary">{order.caution}</p>
              <div className="mt-3 rounded-sm bg-blue-500/8 px-2.5 py-2 text-[11px] text-blue-300">
                {order.sourceRefs?.[0] ? (
                  <button
                    type="button"
                    className="cursor-pointer border-0 bg-transparent p-0 text-left text-[11px] font-semibold text-blue-300 underline-offset-2 hover:underline"
                    onClick={() => {
                      const sourceRef = order.sourceRefs?.[0];
                      if (sourceRef) onOpenManual(sourceRef);
                    }}
                  >
                    📎 출처: {order.source}
                  </button>
                ) : (
                  <>📎 출처: {order.source}</>
                )}
              </div>
            </div>
          </div>

          {!approved && (
            <div className={cn(ui.cardSm, 'flex justify-end gap-2')}>
              <button className={buttonClass('secondary')} onClick={onNavigateResult}>결과 입력으로 이동</button>
              <button className={buttonClass('primary')} onClick={() => setApproved(true)}>✓ 승인 — 작업자에게 전송</button>
            </div>
          )}
          {approved && (
            <div className={cn(ui.cardSm, 'flex items-center justify-between border-green-400/20 bg-green-500/6')}>
              <span className="text-[13px] font-semibold text-green-400">✓ 승인 완료 — 전송 대기 중</span>
              <button
                className={cn(ui.button.base, 'rounded bg-[#25d366] text-white hover:bg-[#21bf5b]')}
                onClick={() => onSendKakao(order)}
              >📱 카카오톡으로 전송</button>
            </div>
          )}
        </div>
      )}

      {status === 'idle' && (
        <div className={cn(ui.card, 'p-10 text-center')}>
          <div className="mb-3 text-4xl">🤖</div>
          <div className="mb-2 text-[15px] font-semibold">AI 작업지시서를 생성합니다</div>
          <div className="mx-auto max-w-[380px] text-[13px] leading-[1.6] text-text-muted">
            Gemini API와 설비 매뉴얼 RAG를 활용해<br />
            <strong className="text-blue-400">{targetEq.name}</strong>의 맞춤 정비 지시서를 자동 생성합니다.<br />
            평균 생성 시간: <strong className="text-text-primary">약 5초</strong>
          </div>
        </div>
      )}
    </div>
  );
}
