import type { EquipmentStatus } from '../types';
import { badgeClass, dotClass } from '../utils/styles';

const MAP: Record<EquipmentStatus, { label: string; badge: 'normal' | 'warn' | 'danger'; dot: 'normal' | 'warn' | 'danger' }> = {
  normal: { label: '정상', badge: 'normal', dot: 'normal' },
  warn:   { label: '경고', badge: 'warn',   dot: 'warn' },
  danger: { label: '위험', badge: 'danger', dot: 'danger' },
};

export function StatusBadge({ status }: { status: EquipmentStatus }) {
  const { label, badge, dot } = MAP[status];
  return (
    <span className={badgeClass(badge)}>
      <span className={dotClass(dot)} />
      {label}
    </span>
  );
}
