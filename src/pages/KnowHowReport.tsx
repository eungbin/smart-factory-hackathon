import { useEffect, useState } from 'react';
import { fetchMonthlyReport, type MonthlyReportResponse } from '../api/reports';
import { MonthlyDowntimeChart } from '../components/charts/MonthlyDowntimeChart';
import { FaultPieChart } from '../components/charts/FaultPieChart';
import { badgeClass, buttonClass, cn, ui } from '../utils/styles';

type ReportData = MonthlyReportResponse['data'];

type KpiProps = {
  label: string;
  value: string | number;
  unit?: string;
  delta?: string;
  deltaDir?: 'good' | 'bad';
  sub?: string;
};

function KpiCard({ label, value, unit, delta, deltaDir, sub }: KpiProps) {
  const dColor =
    deltaDir === 'good' ? 'text-green-400' :
    deltaDir === 'bad' ? 'text-red-400' :
      'text-text-muted';

  return (
    <div className={cn(ui.card, 'flex flex-col gap-1.5')}>
      <div className="text-[11px] text-text-muted">{label}</div>
      <div className="flex items-baseline gap-1">
        <span className="text-[30px] font-black leading-none">{value}</span>
        {unit && <span className="text-xs text-text-muted">{unit}</span>}
      </div>
      {delta && <div className={cn('text-xs font-semibold', dColor)}>{delta}</div>}
      {sub && <div className="text-[11px] text-text-muted">{sub}</div>}
    </div>
  );
}

function getReportStatIndex(report: ReportData) {
  return report.availableMonths.findIndex(item => item.month === report.month);
}

function getPreviousStat(report: ReportData) {
  const currentIndex = getReportStatIndex(report);
  if (currentIndex <= 0) {
    return null;
  }
  return report.monthlyStats[currentIndex - 1] ?? null;
}

function formatSigned(value: number, unit: string) {
  const prefix = value > 0 ? '+' : '';
  return `${prefix}${value}${unit}`;
}

export function KnowHowReport() {
  const [selectedMonth, setSelectedMonth] = useState<string | null>(null);
  const [report, setReport] = useState<ReportData | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    fetchMonthlyReport(selectedMonth, controller.signal)
      .then(response => {
        setReport(response.data);
        setLoadError(null);
      })
      .catch(error => {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return;
        }
        console.error('Failed to load monthly report', error);
        setLoadError('월간 리포트 API 연결에 실패했습니다.');
      });

    return () => controller.abort();
  }, [selectedMonth]);

  if (!report && !loadError) {
    return (
      <div className={cn(ui.card, 'px-5 py-4 text-sm text-text-secondary')}>
        월간 리포트를 불러오는 중입니다.
      </div>
    );
  }

  if (loadError || !report) {
    return (
      <div className="rounded-md border border-red-500/25 bg-red-500/8 px-4 py-3 text-sm text-red-300">
        {loadError ?? '월간 리포트 응답이 비어 있습니다.'}
      </div>
    );
  }

  const currentIndex = getReportStatIndex(report);
  const previousStat = getPreviousStat(report);
  const currentStat = currentIndex >= 0 ? report.monthlyStats[currentIndex] ?? null : null;
  const downtimeDelta = previousStat && currentStat ? currentStat.downtime - previousStat.downtime : 0;
  const preventedDelta = previousStat && currentStat ? currentStat.prevented - previousStat.prevented : 0;
  const mttrDelta = previousStat && currentStat ? currentStat.mttr - previousStat.mttr : 0;

  return (
    <div className="flex animate-fade-in flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="text-[15px] font-bold">월간 노하우 리포트</div>
        <div className="flex gap-1">
          {report.availableMonths.map(item => (
            <button
              key={item.month}
              className={cn(
                buttonClass('ghost', 'sm'),
                'rounded-sm',
                report.month === item.month ? 'bg-blue-500/10 text-blue-400' : 'text-text-muted',
              )}
              onClick={() => setSelectedMonth(item.month)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3">
        <KpiCard
          label="비계획 정지 시간"
          value={report.kpis.unplannedDowntimeHours}
          unit="h"
          delta={previousStat ? `전월 대비 ${formatSigned(downtimeDelta, 'h')}` : undefined}
          deltaDir={downtimeDelta <= 0 ? 'good' : 'bad'}
          sub="월간 리포트 기준"
        />
        <KpiCard
          label="예방 정비 건수"
          value={report.kpis.preventedCount}
          unit="건"
          delta={previousStat ? `전월 대비 ${formatSigned(preventedDelta, '건')}` : undefined}
          deltaDir={preventedDelta >= 0 ? 'good' : 'bad'}
          sub="AI 알림 기반"
        />
        <KpiCard
          label="평균 MTTR"
          value={report.kpis.mttrMinutes}
          unit="분"
          delta={previousStat ? `전월 대비 ${formatSigned(mttrDelta, '분')}` : undefined}
          deltaDir={mttrDelta <= 0 ? 'good' : 'bad'}
          sub="정비 이력 집계"
        />
        <KpiCard
          label="누적 학습 데이터"
          value={report.kpis.learningDataCount}
          unit="건"
          delta="학습 큐 적재"
          deltaDir="good"
          sub="정비 결과 기반"
        />
      </div>

      <div className="grid grid-cols-[3fr_2fr] gap-3.5">
        <div className={ui.card}>
          <div className={ui.sectionTitle}>월별 비계획 정지 시간 추이</div>
          <MonthlyDowntimeChart data={report.monthlyStats} height={200} />
          <div className="mt-2 flex gap-3 text-[11px]">
            <span className="flex items-center gap-1">
              <span className="inline-block size-2.5 rounded-[2px] bg-blue-500" />
              비계획 정지(h)
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block size-2.5 rounded-[2px] bg-green-400" />
              예방 완료(건)
            </span>
          </div>
        </div>
        <div className={ui.card}>
          <div className={ui.sectionTitle}>고장 유형 분포</div>
          <FaultPieChart data={report.faultDistribution} height={200} />
        </div>
      </div>

      <div className={ui.card}>
        <div className={ui.sectionTitle}>AI 생성 인사이트</div>
        <div className="grid grid-cols-2 gap-2.5">
          {report.insights.map((ins, i) => (
            <div
              key={`${ins.title}-${i}`}
              className={cn(
                'rounded border bg-bg-base px-3.5 py-3',
                ins.priority === 'high' ? 'border-red-400/20' : ins.priority === 'medium' ? 'border-amber-400/15' : 'border-border',
              )}
            >
              <div className="mb-1.5 flex items-center gap-2">
                <span className="text-sm">{ins.icon}</span>
                <span className="text-[13px] font-semibold">{ins.title}</span>
              </div>
              <p className="text-xs leading-[1.65] text-text-secondary">{ins.body}</p>
            </div>
          ))}
        </div>
      </div>

      <div className={ui.card}>
        <div className="mb-3 flex items-center justify-between">
          <div className="text-[13px] font-semibold text-text-secondary">자동 추출 노하우 지식 베이스</div>
          <span className={badgeClass('info')}>RAG 인덱스 완료</span>
        </div>
        <div className="flex flex-col gap-2">
          {report.learnedKnowledge.map(k => (
            <div key={k.id} className="flex items-start gap-3 rounded border border-border bg-bg-base px-3.5 py-3">
              <span className={ui.tag}>{k.id}</span>
              <div className="flex-1">
                <div className="mb-1 flex items-center gap-1.5">
                  <span className="text-[11px] text-text-muted">{k.equip}</span>
                  <span className="text-[10px] text-text-muted">·</span>
                  <span className="text-[11px] text-text-muted">{k.date}</span>
                </div>
                <p className="text-[13px] leading-[1.6] text-text-primary">{k.content}</p>
              </div>
              <div className="flex shrink-0 flex-col items-end gap-1">
                <span className="text-[10px] text-text-muted">신뢰도</span>
                <span
                  className={cn(
                    'text-base font-extrabold',
                    k.confidence >= 90 ? 'text-green-400' : k.confidence >= 75 ? 'text-blue-400' : 'text-amber-400',
                  )}
                >
                  {k.confidence}%
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
