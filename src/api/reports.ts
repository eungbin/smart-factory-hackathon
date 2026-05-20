import type {
  FaultDistEntry,
  LearnedKnowledge,
  MonthlyStat,
  ReportInsight,
  ReportKpis,
  ReportMonth,
} from '../types';

export type MonthlyReportResponse = {
  data: {
    month: string;
    availableMonths: ReportMonth[];
    kpis: ReportKpis;
    monthlyStats: MonthlyStat[];
    faultDistribution: FaultDistEntry[];
    insights: ReportInsight[];
    learnedKnowledge: LearnedKnowledge[];
  };
};

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000';

function getApiBaseUrl() {
  return (import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/$/, '');
}

export async function fetchMonthlyReport(month?: string | null, signal?: AbortSignal): Promise<MonthlyReportResponse> {
  const params = new URLSearchParams();
  if (month) {
    params.set('month', month);
  }

  const query = params.toString();
  const response = await fetch(`${getApiBaseUrl()}/api/v1/reports/monthly${query ? `?${query}` : ''}`, { signal });

  if (!response.ok) {
    throw new Error(`Monthly report API request failed: ${response.status}`);
  }

  return response.json() as Promise<MonthlyReportResponse>;
}
