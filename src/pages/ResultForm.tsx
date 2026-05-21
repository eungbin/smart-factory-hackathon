import { useEffect, useState, type FormEvent } from 'react';
import type { Equipment, FaultTypeCode } from '../types';
import { fetchEquipmentList } from '../api/equipment';
import { createMaintenanceRecord } from '../api/maintenance';
import { buttonClass, cn, ui } from '../utils/styles';

type FormState = {
  equipId: number | string;
  date: string;
  tech: string;
  type: string;
  result: string;
  duration: number;
  partsReplaced: string;
  grease: boolean;
  bearing: boolean;
  seal: boolean;
  note: string;
  nextPlan: string;
  actualFaultTypeCode: FaultTypeCode | '';
};

type Props = {
  eq: Equipment;
  onSubmit?: (form: FormState) => void;
};

const FAULT_TYPE_OPTIONS: Array<{ value: FaultTypeCode; label: string }> = [
  { value: 'bearing_fault', label: '베어링 불량' },
  { value: 'belt_loose', label: '벨트 느슨함' },
  { value: 'rotor_unbalance', label: '회전체 불평형' },
  { value: 'shaft_misalignment', label: '축정렬 불량' },
  { value: 'hydraulic_seal', label: '유압 씰 이상' },
  { value: 'normal', label: '이상 없음' },
  { value: 'other', label: '다른 고장 유형' },
];

function faultTypeLabel(value: FaultTypeCode | '') {
  return FAULT_TYPE_OPTIONS.find(option => option.value === value)?.label;
}

export function ResultForm({ eq, onSubmit }: Props) {
  const [form, setForm] = useState<FormState>({
    equipId: eq.id,
    date: new Date().toISOString().slice(0, 10),
    tech: '이민준',
    type: '예방 정비',
    result: '정상',
    duration: 65,
    partsReplaced: '',
    grease: true,
    bearing: false,
    seal: false,
    note: '',
    nextPlan: '',
    actualFaultTypeCode: '',
  });
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [queueId, setQueueId] = useState('');
  const [equipmentList, setEquipmentList] = useState<Equipment[]>([eq]);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const targetEq = equipmentList.find(item => String(item.id) === String(form.equipId)) ?? eq;

  useEffect(() => {
    const controller = new AbortController();

    fetchEquipmentList(controller.signal)
      .then(response => setEquipmentList(response.data.length > 0 ? response.data : [eq]))
      .catch(error => {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return;
        }
        console.error('Failed to load equipment list for result form', error);
      });

    return () => controller.abort();
  }, [eq]);

  function setField<K extends keyof FormState>(k: K, v: FormState[K]) {
    setForm(prev => ({ ...prev, [k]: v }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setSubmitError(null);

    try {
      const response = await createMaintenanceRecord({
        equipmentId: Number(form.equipId),
        date: form.date,
        technicianName: form.tech,
        type: form.type,
        result: form.result,
        duration: form.duration,
        actions: {
          grease: form.grease,
          bearing: form.bearing,
          seal: form.seal,
        },
        partsReplaced: form.partsReplaced,
        actualFaultTypeCode: form.actualFaultTypeCode || undefined,
        aiAccuracyNote: faultTypeLabel(form.actualFaultTypeCode),
        note: form.note,
        nextPlan: form.nextPlan,
      });

      setQueueId(response.data.learningQueueId);
      setSubmitted(true);
      onSubmit?.(form);
    } catch (error) {
      console.error('Failed to submit maintenance result', error);
      setSubmitError('정비 결과 API 저장에 실패했습니다.');
    } finally {
      setSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <div
        className="flex min-h-[400px] animate-fade-in flex-col items-center justify-center gap-4"
      >
        <div className="flex size-16 items-center justify-center rounded-full border-2 border-green-400 bg-green-400/15 text-[28px]">✓</div>
        <div className="text-lg font-bold text-green-400">정비 결과 저장 완료</div>
        <div className="text-center text-[13px] leading-[1.7] text-text-muted">
          입력된 결과가 정비 이력 DB에 저장되었습니다.<br />
          <strong className="text-blue-400">학습 큐</strong>에 적재되어 다음 모델 업데이트에 반영됩니다.
        </div>
        <div className="rounded-md border border-border bg-bg-card px-5 py-3 text-xs leading-[1.8] text-text-secondary">
          <div><strong>설비:</strong> {targetEq.name}</div>
          <div><strong>정비 유형:</strong> {form.type}</div>
          <div><strong>결과:</strong> {form.result}</div>
          <div><strong>소요시간:</strong> {form.duration}분</div>
          <div><strong>학습 큐 ID:</strong> {queueId}</div>
        </div>
        <button className={buttonClass('primary')} onClick={() => setSubmitted(false)}>새 결과 입력</button>
      </div>
    );
  }

  return (
    <div className="flex animate-fade-in flex-col gap-4">
      <div className={cn(ui.cardSm, 'flex items-center justify-between')}>
        <div>
          <div className="text-[15px] font-bold">정비 결과 입력</div>
          <div className="mt-0.5 text-xs text-text-muted">
            완료 후 데이터는 자동으로 <strong className="text-blue-400">학습 큐</strong>에 적재됩니다
          </div>
        </div>
        <div className="flex items-center gap-2 rounded border border-blue-500/20 bg-blue-500/8 px-3.5 py-2 text-xs">
          <span className="text-blue-400">C</span>
          <span className="text-text-secondary">축적 모듈 — 데이터 누적 대기 중</span>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-3.5">
        <div className={ui.card}>
          <div className="mb-3.5 text-[13px] font-semibold text-text-secondary">기본 정보</div>
          <div className="grid grid-cols-3 gap-3.5">
            <div>
              <label className={ui.label}>대상 설비</label>
              <select className={cn(ui.input, 'cursor-pointer')} value={form.equipId} onChange={e => setField('equipId', e.target.value)}>
                {equipmentList.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
              </select>
            </div>
            <div>
              <label className={ui.label}>정비 일시</label>
              <input type="date" className={ui.input} value={form.date} onChange={e => setField('date', e.target.value)} />
            </div>
            <div>
              <label className={ui.label}>담당 기사</label>
              <input type="text" className={ui.input} value={form.tech} onChange={e => setField('tech', e.target.value)} />
            </div>
          </div>
        </div>

        <div className={ui.card}>
          <div className="mb-3.5 text-[13px] font-semibold text-text-secondary">정비 유형 및 결과</div>
          <div className="grid grid-cols-3 gap-3.5">
            <div>
              <label className={ui.label}>정비 유형</label>
              <div className="flex flex-col flex-wrap gap-2">
                {['예방 정비', '긴급 정비', '정기 점검', '부품 교체'].map(v => (
                  <div
                    key={v}
                    className={cn(ui.radioOption, 'min-w-0 text-left', form.type === v && ui.radioSelected)}
                    onClick={() => setField('type', v)}
                  >{v}</div>
                ))}
              </div>
            </div>
            <div>
              <label className={ui.label}>최종 결과</label>
              <div className="flex flex-col flex-wrap gap-2">
                {['정상 복구', '부분 개선', '부품 교체 필요', '재정비 예약'].map(v => {
                  const selected = form.result === v || (v === '정상 복구' && form.result === '정상');
                  return (
                    <div
                      key={v}
                      className={cn(ui.radioOption, 'min-w-0 text-left', selected && ui.radioSelected)}
                      onClick={() => setField('result', v)}
                    >{v}</div>
                  );
                })}
              </div>
            </div>
            <div>
              <div>
                <label className={ui.label}>소요 시간 (분)</label>
                <input
                  type="number"
                  className={ui.input}
                  value={form.duration}
                  onChange={e => setField('duration', Number(e.target.value))}
                  min={5}
                  max={480}
                />
              </div>
              <div className="mt-3">
                <label className={ui.label}>작업 항목</label>
                {([['grease', '그리스 보충'], ['bearing', '베어링 교체'], ['seal', '씰 교체']] as const).map(([k, label]) => (
                  <label key={k} className="mb-1.5 flex cursor-pointer items-center gap-2 text-xs">
                    <input
                      type="checkbox"
                      checked={form[k]}
                      onChange={e => setField(k, e.target.checked)}
                      className="size-3.5 accent-blue-500"
                    />
                    <span className="text-text-secondary">{label}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className={cn(ui.card, 'border-blue-500/15 bg-blue-500/4')}>
          <div className="mb-3.5 text-[13px] font-semibold text-blue-400">
            🤖 AI 예측 정확도 평가 (학습 품질 향상용)
          </div>
          <div className="mb-3 rounded border border-blue-500/15 bg-bg-base px-3 py-2 text-xs text-text-secondary">
            AI 예측: <strong className="text-text-primary">{targetEq.faultType ?? '진단 대기'}</strong>
            {targetEq.faultConf !== null ? <span className="text-blue-300"> {targetEq.faultConf}%</span> : null}
          </div>
          <div className="grid grid-cols-2 gap-3.5">
            <div>
              <label className={ui.label}>실제 고장 유형</label>
              <select
                className={cn(ui.input, 'cursor-pointer')}
                value={form.actualFaultTypeCode}
                onChange={e => setField('actualFaultTypeCode', e.target.value as FaultTypeCode | '')}
              >
                <option value="">선택 (선택 사항)</option>
                {FAULT_TYPE_OPTIONS.map(option => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className={ui.label}>특이사항 / 메모</label>
              <textarea
                className={cn(ui.input, 'min-h-[70px] resize-y')}
                value={form.note}
                onChange={e => setField('note', e.target.value)}
                placeholder="추가 관찰사항, 다음 점검 시 확인 사항 등..."
              />
            </div>
          </div>
        </div>

        {submitError && (
          <div className="rounded-md border border-red-500/25 bg-red-500/8 px-4 py-3 text-sm text-red-300">
            {submitError}
          </div>
        )}

        <div className="flex justify-end gap-2.5">
          <button type="button" className={buttonClass('secondary')}>취소</button>
          <button type="submit" className={buttonClass('primary', 'lg')} disabled={submitting}>
            {submitting ? (
              <>
                <svg className="animate-spin-fast" width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <circle cx="7" cy="7" r="5" stroke="currentColor" strokeWidth="2" strokeDasharray="12 8" />
                </svg>
                {' '}저장 중...
              </>
            ) : '결과 저장 → 학습 큐 적재'}
          </button>
        </div>
      </form>
    </div>
  );
}
