export type EquipmentStatus = 'normal' | 'warn' | 'danger';

export type Sensors = {
  vibration: number;
  temp: number;
  current: number;
  pressure: number;
};

export type Equipment = {
  id: number;
  name: string;
  model: string;
  year: number;
  status: EquipmentStatus;
  rul: number;
  rulMin: number;
  rulMax: number;
  risk: number;
  lastMaint: string;
  nextPlan: string;
  sensors: Sensors;
  faultType: string | null;
  faultConf: number | null;
  faultTop3: FaultCandidate[];
};

export type FaultCandidate = {
  faultTypeCode: string;
  faultType: string;
  probability: number;
};

export type FaultTypeCode =
  | 'normal'
  | 'bearing_fault'
  | 'belt_loose'
  | 'rotor_unbalance'
  | 'shaft_misalignment'
  | 'hydraulic_seal'
  | 'other';

export type SensorHistoryPoint = {
  time: string;
  vibration: number;
  temperature: number;
  current: number;
  pressure: number;
};

export type RulHistoryPoint = {
  date: string;
  rul: number;
  upper: number;
  lower: number;
};

export type MaintHistoryEntry = {
  id: number;
  equipId: number;
  date: string;
  type: string;
  tech: string;
  parts: string;
  result: string;
  duration: number;
  note: string;
};

export type MonthlyStat = {
  month: string;
  downtime: number;
  prevented: number;
  mttr: number;
};

export type FaultDistEntry = {
  name: string;
  value: number;
  color: string;
};

export type ReportMonth = {
  month: string;
  label: string;
};

export type ReportKpis = {
  unplannedDowntimeHours: number;
  preventedCount: number;
  mttrMinutes: number;
  learningDataCount: number;
};

export type ReportInsight = {
  icon: string;
  title: string;
  body: string;
  priority: 'high' | 'medium' | 'low' | 'info';
};

export type LearnedKnowledge = {
  id: string;
  equip: string;
  content: string;
  confidence: number;
  date: string;
};

export type WorkOrderStep = {
  no: number;
  category: '안전' | '진단' | '윤활' | '부품' | '복구' | '기록';
  action: string;
  tool: string;
  time: string;
  safety: boolean;
};

export type WorkOrderPart = {
  name: string;
  qty: string;
  stock: string;
};

export type WorkOrderSourceRef = {
  documentId: number;
  chunkId: number;
  sourceLabel: string;
  heading: string | null;
};

export type WorkOrder = {
  equipId: number;
  equipName: string;
  generatedAt: string;
  rul: string;
  risk: number;
  faultType: string;
  rootSensors: string[];
  source: string;
  sourceRefs?: WorkOrderSourceRef[];
  steps: WorkOrderStep[];
  parts: WorkOrderPart[];
  totalTime: string;
  techLevel: string;
  caution: string;
};

export type WorkOrderSummary = {
  id: number;
  equipId: number;
  equipName: string;
  generatedAt: string;
  rul: string;
  risk: number;
  faultType: string;
  source: string;
  status: string;
  totalTime: string;
  techLevel: string;
};

export type KnowledgeChunk = {
  chunkId: number;
  chunkNo: number;
  heading: string | null;
  body: string;
  metadata: Record<string, unknown>;
};

export type KnowledgeDocumentSummary = {
  documentId: number;
  title: string;
  documentType: string;
  sourceLabel: string;
  equipmentModelId: number | null;
  fileName: string | null;
  fileUri: string | null;
  uploadedAt: string;
};

export type KnowledgeDocumentDetail = KnowledgeDocumentSummary & {
  chunks: KnowledgeChunk[];
};

export type PageId = 'dashboard' | 'detail' | 'workorder' | 'workorders' | 'manuals' | 'result' | 'report';
