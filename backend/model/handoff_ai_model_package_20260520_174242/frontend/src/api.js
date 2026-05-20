const API_BASE = "/api";

export async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    },
    ...options
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `API error ${response.status}`);
  }
  return response.json();
}

export const getAssets = () => api("/assets");
export const getAsset = (assetId) => api(`/assets/${assetId}`);
export const predictRul = (assetId, window) =>
  api("/predict/rul", {
    method: "POST",
    body: JSON.stringify({ asset_id: assetId, window })
  });
export const predictHealth = (assetId, window) =>
  api("/predict/health", {
    method: "POST",
    body: JSON.stringify({ asset_id: assetId, window })
  });
export const createWorkOrder = (assetId, prediction) =>
  api("/work-orders", {
    method: "POST",
    body: JSON.stringify({ asset_id: assetId, prediction, requested_by: "김영수 반장" })
  });
export const dispatchWorkOrder = (workOrderId) =>
  api(`/work-orders/${workOrderId}/dispatch`, { method: "POST" });
export const createMaintenanceEvent = (payload) =>
  api("/maintenance-events", { method: "POST", body: JSON.stringify(payload) });
export const getKnowledgeReport = () => api("/reports/knowledge");
export const getDatasets = () => api("/datasets");
