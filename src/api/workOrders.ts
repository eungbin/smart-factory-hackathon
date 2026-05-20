import type { WorkOrder } from '../types';

export type GeneratedWorkOrder = WorkOrder & {
  id: number;
  status: string;
};

export type GenerateWorkOrderResponse = {
  data: GeneratedWorkOrder;
};

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000';

function getApiBaseUrl() {
  return (import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/$/, '');
}

export async function generateWorkOrder(equipmentId: number): Promise<GenerateWorkOrderResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/work-orders/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ equipmentId }),
  });

  if (!response.ok) {
    throw new Error(`Work order API request failed: ${response.status}`);
  }

  return response.json() as Promise<GenerateWorkOrderResponse>;
}
