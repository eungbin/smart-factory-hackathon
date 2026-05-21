import type { FaultTypeCode } from '../types';

export type MaintenanceRecordPayload = {
  equipmentId: number;
  date: string;
  technicianName: string;
  type: string;
  result: string;
  duration: number;
  actions: {
    grease: boolean;
    bearing: boolean;
    seal: boolean;
  };
  partsReplaced: string;
  actualFaultTypeCode?: FaultTypeCode;
  aiAccuracyNote?: string;
  note?: string;
  nextPlan?: string;
};

export type MaintenanceRecordResponse = {
  data: {
    maintenanceRecordId: number;
    learningQueueId: string;
    saved: boolean;
  };
};

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000';

function getApiBaseUrl() {
  return (import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/$/, '');
}

export async function createMaintenanceRecord(payload: MaintenanceRecordPayload): Promise<MaintenanceRecordResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/maintenance-records`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Maintenance record API request failed: ${response.status}`);
  }

  return response.json() as Promise<MaintenanceRecordResponse>;
}
