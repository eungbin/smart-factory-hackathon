import type { Equipment } from '../types';

export type DashboardSummary = {
  totalEquipment: number;
  dangerCount: number;
  warnCount: number;
  normalCount: number;
  monthlyUptimePct: number;
};

export type DashboardAlert = {
  id: number;
  equipmentId: number;
  equipmentName: string;
  level: 'warn' | 'danger';
  title: string;
  rulHours: number;
  rulRangeText: string;
  riskPct: number;
  faultType: string | null;
};

export type DashboardResponse = {
  data: {
    summary: DashboardSummary;
    alerts: DashboardAlert[];
    equipment: Equipment[];
  };
};

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000';

function getApiBaseUrl() {
  return (import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/$/, '');
}

export async function fetchDashboard(signal?: AbortSignal): Promise<DashboardResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/dashboard`, { signal });

  if (!response.ok) {
    throw new Error(`Dashboard API request failed: ${response.status}`);
  }

  return response.json() as Promise<DashboardResponse>;
}
