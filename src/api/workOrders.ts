import type { WorkOrder, WorkOrderSummary } from '../types';

export type GeneratedWorkOrder = WorkOrder & {
  id: number;
  status: string;
};

export type GenerateWorkOrderResponse = {
  data: GeneratedWorkOrder;
};

export type WorkOrdersResponse = {
  data: WorkOrderSummary[];
  page: {
    limit: number;
    nextCursor: string | null;
  };
};

export type WorkOrderResponse = {
  data: GeneratedWorkOrder;
};

export type SendKakaoWorkOrderResponse = {
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

export async function fetchWorkOrders(signal?: AbortSignal): Promise<WorkOrdersResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/work-orders`, { signal });

  if (!response.ok) {
    throw new Error(`Work orders API request failed: ${response.status}`);
  }

  return response.json() as Promise<WorkOrdersResponse>;
}

export async function fetchWorkOrder(workOrderId: number, signal?: AbortSignal): Promise<WorkOrderResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/work-orders/${workOrderId}`, { signal });

  if (!response.ok) {
    throw new Error(`Work order detail API request failed: ${response.status}`);
  }

  return response.json() as Promise<WorkOrderResponse>;
}

export async function sendKakaoWorkOrder(workOrderId: number): Promise<SendKakaoWorkOrderResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/work-orders/${workOrderId}/send-kakao`, {
    method: 'POST',
  });

  if (!response.ok) {
    throw new Error(`Work order Kakao send request failed: ${response.status}`);
  }

  return response.json() as Promise<SendKakaoWorkOrderResponse>;
}
