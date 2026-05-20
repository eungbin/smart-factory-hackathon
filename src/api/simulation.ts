import type { EquipmentStatus } from '../types';

export type SimulationPrediction = {
  predictionRunId: number;
  equipmentId: number;
  status: EquipmentStatus;
  rul: number;
  rulMin: number;
  rulMax: number;
  risk: number;
  faultTypeCode: string | null;
  faultType: string | null;
  faultConfidence: number | null;
  faultProbabilities: Array<{
    faultTypeCode: string;
    faultType: string;
    probability: number;
  }>;
  rootSensors: Array<{
    sensorName: string;
    importance: number;
    direction: string;
    displayText: string;
  }>;
  createdAt: string;
};

export type SimulationTickResponse = {
  data: {
    insertedReadings: number;
    predictions: SimulationPrediction[];
  };
};

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000';

function getApiBaseUrl() {
  return (import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/$/, '');
}

export async function runSimulationTick(equipmentId?: number): Promise<SimulationTickResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/simulation/tick`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(equipmentId ? { equipmentId } : {}),
  });

  if (!response.ok) {
    throw new Error(`Simulation API request failed: ${response.status}`);
  }

  return response.json() as Promise<SimulationTickResponse>;
}
