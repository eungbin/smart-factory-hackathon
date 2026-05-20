import type { Equipment, MaintHistoryEntry, RulHistoryPoint, SensorHistoryPoint } from '../types';

export type EquipmentListResponse = {
  data: Equipment[];
  page: {
    limit: number;
    nextCursor: string | null;
  };
};

export type EquipmentResponse = {
  data: Equipment;
};

export type SensorHistoryResponse = {
  data: SensorHistoryPoint[];
};

export type RulHistoryResponse = {
  data: RulHistoryPoint[];
};

export type MaintenanceHistoryResponse = {
  data: MaintHistoryEntry[];
};

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000';

function getApiBaseUrl() {
  return (import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/$/, '');
}

export async function fetchEquipmentList(signal?: AbortSignal): Promise<EquipmentListResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/equipment`, { signal });

  if (!response.ok) {
    throw new Error(`Equipment API request failed: ${response.status}`);
  }

  return response.json() as Promise<EquipmentListResponse>;
}

export async function fetchEquipment(equipmentId: number, signal?: AbortSignal): Promise<EquipmentResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/equipment/${equipmentId}`, { signal });

  if (!response.ok) {
    throw new Error(`Equipment detail API request failed: ${response.status}`);
  }

  return response.json() as Promise<EquipmentResponse>;
}

export async function fetchEquipmentSensorHistory(equipmentId: number, signal?: AbortSignal): Promise<SensorHistoryResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/equipment/${equipmentId}/sensor-history`, { signal });

  if (!response.ok) {
    throw new Error(`Sensor history API request failed: ${response.status}`);
  }

  return response.json() as Promise<SensorHistoryResponse>;
}

export async function fetchEquipmentRulHistory(equipmentId: number, signal?: AbortSignal): Promise<RulHistoryResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/equipment/${equipmentId}/rul-history`, { signal });

  if (!response.ok) {
    throw new Error(`RUL history API request failed: ${response.status}`);
  }

  return response.json() as Promise<RulHistoryResponse>;
}

export async function fetchEquipmentMaintenanceHistory(equipmentId: number, signal?: AbortSignal): Promise<MaintenanceHistoryResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/equipment/${equipmentId}/maintenance-history`, { signal });

  if (!response.ok) {
    throw new Error(`Maintenance history API request failed: ${response.status}`);
  }

  return response.json() as Promise<MaintenanceHistoryResponse>;
}
