import type { Equipment } from '../types';
import { fetchEquipment, fetchEquipmentList, type EquipmentListResponse, type EquipmentResponse } from './equipment';

export async function equipmentApiContract(): Promise<Equipment> {
  const listResponse: EquipmentListResponse = await fetchEquipmentList();
  const first = listResponse.data[0];
  const detailResponse: EquipmentResponse = await fetchEquipment(first.id);

  return detailResponse.data;
}
