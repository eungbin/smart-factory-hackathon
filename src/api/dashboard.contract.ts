import type { Equipment } from '../types';
import { fetchDashboard, type DashboardResponse } from './dashboard';

export async function dashboardApiContract(): Promise<Equipment[]> {
  const response: DashboardResponse = await fetchDashboard();
  const totalEquipment: number = response.data.summary.totalEquipment;
  const alertLevels: Array<'warn' | 'danger'> = response.data.alerts.map(alert => alert.level);

  void totalEquipment;
  void alertLevels;

  return response.data.equipment;
}
