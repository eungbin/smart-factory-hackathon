import { useState } from 'react';
import type { WorkOrder } from '../types';
import { buttonClass, cn, ui } from '../utils/styles';

type Props = { order: WorkOrder | null; onClose: () => void };

function formatKstTime(date: Date) {
  return new Intl.DateTimeFormat('ko-KR', {
    timeZone: 'Asia/Seoul',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date);
}

export function KakaoModal({ order, onClose }: Props) {
  const [sent, setSent] = useState(false);
  const [sending, setSending] = useState(false);

  function handleSend() {
    setSending(true);
    setTimeout(() => {
      setSending(false);
      setSent(true);
    }, 1200);
  }

  const msgLines = [
    '[공장지기] 정비 작업지시서',
    '',
    `📍 ${order?.equipName ?? '3호 사출기 (LS240-B)'}`,
    `🔴 고장 위험도: ${order?.risk ?? 78}% | RUL: ${order?.rul ?? '72h (±24h)'}`,
    `🔧 AI 진단: ${order?.faultType ?? '베어링 불량 78%'}`,
    '',
    '▶ 작업 개요',
    '• 베어링 부위 육안 점검 및 그리스 교체',
    '• 전원 LOTO 후 작업 (안전 필수)',
    '• 소요 시간: 약 65분',
    '',
    '📎 매뉴얼 §4.3 기반',
    '✅ 완료 후 결과 입력 必',
    '',
    '공장지기 대시보드 → 결과 입력',
  ];

  function lineClass(line: string) {
    const isRed = line.startsWith('🔴');
    const isGreen = line.startsWith('✅');
    return cn(
      'text-xs leading-[1.8]',
      line.startsWith('[') || line.startsWith('▶') ? 'font-bold' : 'font-normal',
      isRed ? 'text-red-600' : isGreen ? 'text-green-600' : 'text-slate-800',
    );
  }

  return (
    <div
      className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/75"
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="w-[380px] animate-fade-in overflow-hidden rounded-lg border border-border bg-bg-panel shadow-[0_24px_80px_rgba(0,0,0,0.5)]">
        <div className="flex items-center gap-2.5 bg-[#FEE500] px-5 py-3.5">
          <div className="flex size-8 items-center justify-center rounded bg-[#3C1E1E] text-lg">💬</div>
          <div>
            <div className="text-sm font-extrabold text-[#3C1E1E]">KakaoTalk 메시지 미리보기</div>
            <div className="text-[11px] text-[#5C3E2E]">공장지기 비즈메시지 (데모)</div>
          </div>
          <button
            onClick={onClose}
            className="ml-auto cursor-pointer border-0 bg-transparent text-lg text-[#3C1E1E]"
          >×</button>
        </div>

        <div className="p-5">
          <div className="mb-4 flex gap-2.5">
            <div className="flex size-9 shrink-0 items-center justify-center rounded bg-[#FEE500] text-base">⚙</div>
            <div className="flex-1">
              <div className="mb-1 text-[11px] text-text-muted">공장지기</div>
              <div className="rounded-[0_12px_12px_12px] border border-slate-200 bg-white px-3.5 py-3">
                {msgLines.map((line, i) => (
                  <div key={i} className={lineClass(line)}>
                    {line || <span>&nbsp;</span>}
                  </div>
                ))}
              </div>
              <div className="mt-1 text-right text-[10px] text-text-muted">
                {formatKstTime(new Date())}
              </div>
            </div>
          </div>

          <div className="mb-3.5 rounded border border-border bg-bg-card px-3.5 py-2.5 text-xs">
            <span className="text-text-muted">수신자: </span>
            <strong>이민준 (정비 담당)</strong>
            <span className="ml-2 text-text-muted">010-xxxx-xxxx</span>
          </div>

          {!sent ? (
            <button
              className={cn(ui.button.base, 'w-full bg-[#FEE500] p-3 text-sm font-extrabold text-[#3C1E1E] hover:bg-[#F6DA00]')}
              onClick={handleSend}
              disabled={sending}
            >
              {sending ? (
                <>
                  <svg className="animate-spin-fast" width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <circle cx="7" cy="7" r="5" stroke="currentColor" strokeWidth="2" strokeDasharray="12 8" />
                  </svg>
                  {' '}전송 중...
                </>
              ) : '📱 카카오톡으로 전송'}
            </button>
          ) : (
            <div className="p-3 text-center">
              <div className="mb-1.5 text-[22px]">✅</div>
              <div className="text-sm font-bold text-green-400">전송 완료!</div>
              <div className="mt-1 text-xs text-text-muted">이민준 기사에게 작업지시서가 전달되었습니다.</div>
              <button className={cn(buttonClass('ghost', 'sm'), 'mt-2.5')} onClick={onClose}>닫기</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
