import { useEffect, useState } from 'react';
import { fetchWorkOrder, fetchWorkOrders, type GeneratedWorkOrder } from '../api/workOrders';
import type { WorkOrderSourceRef, WorkOrderSummary } from '../types';
import { badgeClass, buttonClass, cn, ui } from '../utils/styles';

type Props = {
  selectedWorkOrderId: number | null;
  onSelectWorkOrder: (workOrderId: number) => void;
  onCreateNew: () => void;
  onOpenManual: (sourceRef: WorkOrderSourceRef) => void;
};

function statusLabel(status: string) {
  if (status === 'generated') return '생성됨';
  if (status === 'approved') return '승인됨';
  if (status === 'sent') return '전송됨';
  if (status === 'completed') return '완료';
  return status;
}

export function WorkOrderManagement({ selectedWorkOrderId, onSelectWorkOrder, onCreateNew, onOpenManual }: Props) {
  const [orders, setOrders] = useState<WorkOrderSummary[]>([]);
  const [detail, setDetail] = useState<GeneratedWorkOrder | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    fetchWorkOrders(controller.signal)
      .then(response => {
        setOrders(response.data);
        setLoadError(null);
        if (!selectedWorkOrderId && response.data[0]) {
          onSelectWorkOrder(response.data[0].id);
        }
      })
      .catch(error => {
        if (error instanceof DOMException && error.name === 'AbortError') return;
        console.error('Failed to load work orders', error);
        setLoadError('작업지시서 목록을 불러오지 못했습니다.');
      })
      .finally(() => setLoadingList(false));

    return () => controller.abort();
  }, [onSelectWorkOrder, selectedWorkOrderId]);

  useEffect(() => {
    if (!selectedWorkOrderId) return;

    const controller = new AbortController();

    fetchWorkOrder(selectedWorkOrderId, controller.signal)
      .then(response => {
        setDetail(response.data);
        setLoadError(null);
      })
      .catch(error => {
        if (error instanceof DOMException && error.name === 'AbortError') return;
        console.error('Failed to load work order detail', error);
        setLoadError('작업지시서 상세를 불러오지 못했습니다.');
      });

    return () => controller.abort();
  }, [selectedWorkOrderId]);

  if (loadingList) {
    return <div className={cn(ui.card, 'px-5 py-4 text-sm text-text-secondary')}>작업지시서 목록을 불러오는 중입니다.</div>;
  }

  if (loadError) {
    return (
      <div className="rounded-md border border-red-500/25 bg-red-500/8 px-4 py-3 text-sm text-red-300">
        {loadError}
      </div>
    );
  }

  if (orders.length === 0) {
    return (
      <div className={cn(ui.card, 'flex items-center justify-between px-5 py-4')}>
        <span className="text-sm text-text-secondary">생성된 작업지시서가 없습니다.</span>
        <button className={buttonClass('primary')} onClick={onCreateNew}>새 작업지시서 생성</button>
      </div>
    );
  }

  const showingSelectedDetail = Boolean(selectedWorkOrderId && detail?.id === selectedWorkOrderId);

  return (
    <div className="grid animate-fade-in grid-cols-[360px_minmax(0,1fr)] gap-4">
      <div className={cn(ui.card, 'p-0')}>
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div>
            <div className="text-[13px] font-semibold text-text-secondary">작업지시서 목록</div>
            <div className="mt-0.5 text-[11px] text-text-muted">{orders.length}건</div>
          </div>
          <button className={buttonClass('secondary', 'sm')} onClick={onCreateNew}>새 생성</button>
        </div>
        <div className="flex max-h-[calc(100vh-190px)] flex-col overflow-y-auto">
          {orders.map(order => {
            const selected = order.id === selectedWorkOrderId;
            return (
              <button
                key={order.id}
                type="button"
                className={cn(
                  'border-b border-border bg-transparent px-4 py-3 text-left transition-colors hover:bg-bg-card-hover',
                  selected && 'bg-blue-500/10',
                )}
                onClick={() => onSelectWorkOrder(order.id)}
              >
                <div className="mb-1 flex items-center justify-between gap-2">
                  <span className={cn('text-[13px] font-semibold', selected ? 'text-blue-400' : 'text-text-primary')}>
                    WO-{String(order.id).padStart(5, '0')}
                  </span>
                  <span className={badgeClass(order.status === 'completed' ? 'normal' : 'info')}>{statusLabel(order.status)}</span>
                </div>
                <div className="text-xs text-text-primary">{order.equipName}</div>
                <div className="mt-1 text-[11px] text-text-muted">{order.generatedAt} · 위험도 {order.risk}%</div>
              </button>
            );
          })}
        </div>
      </div>

      <div className={ui.card}>
        {!showingSelectedDetail && <div className="text-sm text-text-secondary">작업지시서 상세를 불러오는 중입니다.</div>}
        {showingSelectedDetail && detail && (
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
              <div>
                <div className="text-lg font-bold text-text-primary">WO-{String(detail.id).padStart(5, '0')}</div>
                <div className="mt-1 text-xs text-text-muted">{detail.equipName} · {detail.generatedAt}</div>
              </div>
              <span className={badgeClass('info')}>{statusLabel(detail.status)}</span>
            </div>

            <div className="grid grid-cols-4 gap-2.5 text-xs">
              <div className={cn(ui.cardSm, 'bg-bg-base')}>
                <div className="text-text-muted">RUL</div>
                <div className="mt-1 font-semibold text-text-primary">{detail.rul}</div>
              </div>
              <div className={cn(ui.cardSm, 'bg-bg-base')}>
                <div className="text-text-muted">위험도</div>
                <div className="mt-1 font-semibold text-red-400">{detail.risk}%</div>
              </div>
              <div className={cn(ui.cardSm, 'bg-bg-base')}>
                <div className="text-text-muted">소요 시간</div>
                <div className="mt-1 font-semibold text-text-primary">{detail.totalTime}</div>
              </div>
              <div className={cn(ui.cardSm, 'bg-bg-base')}>
                <div className="text-text-muted">기술 등급</div>
                <div className="mt-1 font-semibold text-text-primary">{detail.techLevel}</div>
              </div>
            </div>

            <div>
              <div className={ui.sectionTitle}>AI 진단</div>
              <div className="rounded border border-border bg-bg-base px-3.5 py-3 text-[13px] text-text-secondary">
                <div><strong className="text-text-primary">{detail.faultType}</strong></div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {detail.rootSensors.map(sensor => <span key={sensor} className={ui.tag}>{sensor}</span>)}
                </div>
              </div>
            </div>

            <div>
              <div className={ui.sectionTitle}>작업 절차</div>
              <div className="flex flex-col gap-2">
                {detail.steps.map(step => (
                  <div key={step.no} className="rounded border border-border bg-bg-base px-3.5 py-3">
                    <div className="mb-1 flex items-center gap-2">
                      <span className={ui.tag}>{step.category}</span>
                      <span className="text-[11px] text-text-muted">{step.time}</span>
                      {step.safety && <span className="text-[11px] font-semibold text-red-400">안전 필수</span>}
                    </div>
                    <div className="text-[13px] text-text-primary">{step.no}. {step.action}</div>
                    <div className="mt-1 text-[11px] text-text-muted">도구: {step.tool}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className={ui.sectionTitle}>부품</div>
                <div className="rounded border border-border bg-bg-base px-3.5 py-2">
                  {detail.parts.map(part => (
                    <div key={`${part.name}-${part.qty}`} className="flex justify-between border-b border-border py-2 text-xs last:border-b-0">
                      <span className="text-text-primary">{part.name}</span>
                      <span className="text-text-muted">{part.qty} · {part.stock}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <div className={ui.sectionTitle}>출처</div>
                <div className="rounded border border-blue-500/15 bg-blue-500/6 px-3.5 py-3 text-xs text-blue-300">
                  {detail.sourceRefs?.[0] ? (
                    <button
                      type="button"
                      className="cursor-pointer border-0 bg-transparent p-0 text-left font-semibold text-blue-300 underline-offset-2 hover:underline"
                      onClick={() => {
                        const sourceRef = detail.sourceRefs?.[0];
                        if (sourceRef) onOpenManual(sourceRef);
                      }}
                    >
                      {detail.source}
                    </button>
                  ) : detail.source}
                </div>
                <div className="mt-3 rounded border border-red-400/15 bg-red-400/5 px-3.5 py-3 text-xs leading-[1.7] text-text-secondary">
                  {detail.caution}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
