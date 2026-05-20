import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  Database,
  FileText,
  Gauge,
  History,
  Send,
  Wrench
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import {
  createMaintenanceEvent,
  createWorkOrder,
  dispatchWorkOrder,
  getAsset,
  getAssets,
  getDatasets,
  getKnowledgeReport,
  predictHealth
} from "./api";

const statusLabel = {
  normal: "정상",
  watch: "관찰",
  critical: "주의"
};

const statusClass = {
  normal: "status-normal",
  watch: "status-watch",
  critical: "status-critical"
};

function App() {
  const [assets, setAssets] = useState([]);
  const [selectedId, setSelectedId] = useState("INJ-03");
  const [asset, setAsset] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [fault, setFault] = useState(null);
  const [workOrder, setWorkOrder] = useState(null);
  const [dispatchPreview, setDispatchPreview] = useState(null);
  const [report, setReport] = useState(null);
  const [datasets, setDatasets] = useState(null);
  const [form, setForm] = useState({
    worker: "박민준",
    result: "그리스 보충 및 커플링 체결 상태 확인 완료",
    parts_replaced: "교체 부품 없음",
    downtime_minutes: 28,
    comments: "진동 RMS 재측정값 3.18mm/s. 30분 후 재확인 예정.",
    follow_up_needed: true
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function bootstrap() {
      const [assetList, datasetInfo, knowledge] = await Promise.all([
        getAssets(),
        getDatasets(),
        getKnowledgeReport()
      ]);
      setAssets(assetList);
      setDatasets(datasetInfo);
      setReport(knowledge);
      setLoading(false);
    }
    bootstrap().catch(console.error);
  }, []);

  useEffect(() => {
    let disposed = false;
    async function refreshAssetHealth() {
      const detail = await getAsset(selectedId);
      if (disposed) return;
      setAsset(detail);
      const result = await predictHealth(detail.asset_id, detail.sensor_window);
      if (disposed) return;
      setPrediction(result.rul);
      setFault(result.fault);
    }
    setWorkOrder(null);
    setDispatchPreview(null);
    refreshAssetHealth().catch(console.error);
    const timer = window.setInterval(() => {
      refreshAssetHealth().catch(console.error);
    }, 3000);
    return () => {
      disposed = true;
      window.clearInterval(timer);
    };
  }, [selectedId]);

  const chartData = useMemo(() => {
    if (!asset?.sensors?.length) return [];
    return asset.sensors[0].series.map((value, index) => ({
      cycle: index + 1,
      vibration: value,
      current: asset.sensors[1]?.series[index] ?? 0,
      temp: asset.sensors[2]?.series[index] ?? 0
    }));
  }, [asset]);

  const predictionSourceDetail = useMemo(() => {
    if (!prediction?.cmapss_subset) return prediction?.rul_source ?? "factory simulator";
    return `${prediction.rul_source} · ${prediction.cmapss_subset} unit ${prediction.cmapss_unit} · cycle ${prediction.cmapss_last_cycle}`;
  }, [prediction]);

  async function handleGenerateWorkOrder() {
    const order = await createWorkOrder(selectedId, prediction);
    setWorkOrder(order);
  }

  async function handleDispatch() {
    if (!workOrder) return;
    const response = await dispatchWorkOrder(workOrder.id);
    setDispatchPreview(response);
  }

  async function handleMaintenanceSubmit(event) {
    event.preventDefault();
    if (!asset) return;
    await createMaintenanceEvent({
      ...form,
      asset_id: asset.asset_id,
      work_order_id: workOrder?.id ?? null,
      downtime_minutes: Number(form.downtime_minutes)
    });
    const updated = await getKnowledgeReport();
    setReport(updated);
  }

  if (loading || !asset || !prediction || !fault) {
    return (
      <main className="screen center bg-slate-100 text-ink">
        <Activity className="spin" size={28} />
        <span>공장지기 데이터를 불러오는 중</span>
      </main>
    );
  }

  return (
    <main className="screen bg-slate-100 text-ink">
      <header className="topbar">
        <div>
          <p className="eyebrow">중소 제조사 예지보전 운영 플랫폼</p>
          <h1>공장지기</h1>
        </div>
        <div className="top-actions">
          <span className="live-dot" />
          <span>CSV 센서 스트림</span>
          <span>모델 {prediction.model_version}</span>
          <span>{predictionSourceDetail}</span>
        </div>
      </header>

      <section className="alert-band">
        <AlertTriangle size={20} />
        <strong>{asset.name} 점검 권장</strong>
        <span>RUL {prediction.rul_hours}h</span>
        <span>72h 위험도 {prediction.risk_72h}%</span>
        <span>{fault.fault_label} {(fault.fault_probability * 100).toFixed(0)}%</span>
        {prediction.cmapss_subset && <span>{prediction.cmapss_subset} unit {prediction.cmapss_unit}</span>}
        <button onClick={handleGenerateWorkOrder}>
          <FileText size={18} />
          지시서 생성
        </button>
      </section>

      <section className="layout">
        <aside className="asset-list">
          <div className="section-title">
            <Gauge size={18} />
            설비 8대
          </div>
          {assets.map((item) => (
            <button
              key={item.asset_id}
              className={`asset-row ${selectedId === item.asset_id ? "selected" : ""}`}
              onClick={() => setSelectedId(item.asset_id)}
            >
              <span className={`status-pill ${statusClass[item.status]}`}>{statusLabel[item.status]}</span>
              <span>
                <strong>{item.name}</strong>
                <small>{item.primary_issue}</small>
              </span>
              <b>{item.risk_72h}%</b>
            </button>
          ))}
        </aside>

        <section className="main-grid">
          <div className="metrics">
            <Metric icon={Gauge} label="잔여 가동시간" value={`${prediction.rul_hours}h`} detail={`${prediction.cmapss_subset ?? "SIM"} · 신뢰구간 ${prediction.confidence_interval[0]}~${prediction.confidence_interval[1]}h`} />
            <Metric icon={AlertTriangle} label="72h 고장 위험도" value={`${prediction.risk_72h}%`} detail={asset.primary_issue} tone={asset.status} />
            <Metric icon={Activity} label="고장 분류" value={fault.fault_label} detail={`confidence ${(fault.fault_probability * 100).toFixed(0)}% · ${fault.model_version}`} tone={fault.is_fault ? "watch" : "normal"} />
            <Metric icon={Database} label="학습 큐" value={`${report?.training_queue_count ?? 0}건`} detail="정비 결과가 재학습 후보로 적재" />
          </div>

          <section className="panel wide">
            <div className="section-title">
              <Activity size={18} />
              근거 센서 추세
            </div>
            <div className="chart">
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="cycle" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="vibration" name="진동 RMS" stroke="#b91c1c" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="current" name="전류 변동성" stroke="#0f766e" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="temp" name="유압 온도" stroke="#2563eb" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className="panel">
            <div className="section-title">
              <AlertTriangle size={18} />
              고장 분류 결과
            </div>
            <FaultView fault={fault} />
          </section>

          <section className="panel">
            <div className="section-title">
              <ClipboardCheck size={18} />
              예측 근거
            </div>
            <div className="sensor-stack">
              {prediction.contributing_sensors.map((sensor) => (
                <div className="sensor-row" key={sensor.key}>
                  <span>
                    <strong>{sensor.label}</strong>
                    <small>기준 {sensor.baseline}{sensor.unit} → 현재 {sensor.current}{sensor.unit}</small>
                  </span>
                  <b>{sensor.change_pct > 0 ? "+" : ""}{sensor.change_pct}%</b>
                </div>
              ))}
            </div>
          </section>

          <section className="panel">
            <div className="section-title">
              <Database size={18} />
              데이터셋 역할
            </div>
            <DatasetNote datasets={datasets} prediction={prediction} />
          </section>

          <section className="panel wide">
            <div className="section-title">
              <FileText size={18} />
              작업지시서
            </div>
            {workOrder ? (
              <WorkOrderView order={workOrder} onDispatch={handleDispatch} dispatchPreview={dispatchPreview} />
            ) : (
              <div className="empty-state">
                <FileText size={24} />
                <span>위험 설비의 예측 결과를 기반으로 매뉴얼 출처가 포함된 지시서를 생성하세요.</span>
                <button onClick={handleGenerateWorkOrder}>지시서 생성</button>
              </div>
            )}
          </section>

          <section className="panel">
            <div className="section-title">
              <Wrench size={18} />
              결과 입력
            </div>
            <MaintenanceForm form={form} setForm={setForm} onSubmit={handleMaintenanceSubmit} />
          </section>

          <section className="panel">
            <div className="section-title">
              <History size={18} />
              노하우 리포트
            </div>
            <KnowledgeReport report={report} />
          </section>
        </section>
      </section>
    </main>
  );
}

function Metric({ icon: Icon, label, value, detail, tone = "normal" }) {
  return (
    <div className={`metric ${tone}`}>
      <Icon size={19} />
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}

function DatasetNote({ datasets, prediction }) {
  if (!datasets) return null;
  return (
    <div className="dataset-note">
      {prediction?.cmapss_subset && (
        <>
          <strong>현재 RUL 매핑</strong>
          <p>{prediction.cmapss_subset} test unit {prediction.cmapss_unit}, last cycle {prediction.cmapss_last_cycle}. 통합 모델 예측값을 데모 설비 RUL로 매핑.</p>
        </>
      )}
      <strong>{datasets.cmapss.name}</strong>
      <p>{datasets.cmapss.role}. 윈도우 {datasets.cmapss.window_size} cycle 기준.</p>
      <strong>{datasets.aihub.name}</strong>
      <p>{datasets.aihub.role}. {datasets.aihub.label_policy}</p>
    </div>
  );
}

function FaultView({ fault }) {
  return (
    <div className="fault-view">
      <div className={`fault-summary ${fault.is_fault ? "watch" : "normal"}`}>
        <strong>{fault.fault_label}</strong>
        <span>{(fault.fault_probability * 100).toFixed(0)}%</span>
      </div>
      <div className="fault-bars">
        {fault.top_classes.map((item) => (
          <div className="fault-bar" key={item.code}>
            <span>{item.label}</span>
            <div>
              <i style={{ width: `${Math.round(item.probability * 100)}%` }} />
            </div>
            <b>{Math.round(item.probability * 100)}%</b>
          </div>
        ))}
      </div>
      <div className="fault-evidence">
        {fault.evidence.map((item) => (
          <span key={item}>{item}</span>
        ))}
      </div>
      <small>{fault.source}</small>
    </div>
  );
}

function WorkOrderView({ order, onDispatch, dispatchPreview }) {
  return (
    <div className="work-order">
      <div className="work-head">
        <span className={`status-pill ${statusClass[order.severity]}`}>{statusLabel[order.severity]}</span>
        <strong>{order.id}</strong>
        <small>{order.estimated_minutes}분 예상</small>
        <button onClick={onDispatch}>
          <Send size={17} />
          전송
        </button>
      </div>
      <p>{order.summary}</p>
      <div className="two-col">
        <ListBlock title="점검 부위" items={order.inspection_points} />
        <ListBlock title="안전수칙" items={order.safety_rules} />
        <ListBlock title="도구" items={order.tools} />
        <ListBlock title="체크리스트" items={order.checklist} />
      </div>
      <div className="sources">
        {order.manual_sources.map((source) => (
          <span key={`${source.source}-${source.title}`}>{source.source} · {source.title}</span>
        ))}
      </div>
      {dispatchPreview && (
        <div className="dispatch-preview">
          <CheckCircle2 size={18} />
          <span>{dispatchPreview.preview}</span>
        </div>
      )}
    </div>
  );
}

function ListBlock({ title, items }) {
  return (
    <div className="list-block">
      <strong>{title}</strong>
      {items.map((item) => (
        <span key={item}>{item}</span>
      ))}
    </div>
  );
}

function MaintenanceForm({ form, setForm, onSubmit }) {
  function update(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
  }
  return (
    <form className="maintenance-form" onSubmit={onSubmit}>
      <label>
        작업자
        <input value={form.worker} onChange={(event) => update("worker", event.target.value)} />
      </label>
      <label>
        조치 결과
        <textarea value={form.result} onChange={(event) => update("result", event.target.value)} rows={3} />
      </label>
      <label>
        교체 부품
        <input value={form.parts_replaced} onChange={(event) => update("parts_replaced", event.target.value)} />
      </label>
      <label>
        정지 시간
        <input type="number" value={form.downtime_minutes} onChange={(event) => update("downtime_minutes", event.target.value)} />
      </label>
      <label>
        코멘트
        <textarea value={form.comments} onChange={(event) => update("comments", event.target.value)} rows={3} />
      </label>
      <label className="checkline">
        <input type="checkbox" checked={form.follow_up_needed} onChange={(event) => update("follow_up_needed", event.target.checked)} />
        후속 확인 필요
      </label>
      <button type="submit">
        <ClipboardCheck size={17} />
        결과 저장
      </button>
    </form>
  );
}

function KnowledgeReport({ report }) {
  const data = report?.top_failure_modes ?? [];
  return (
    <div className="report">
      <div className="report-numbers">
        <span>
          <strong>{report?.estimated_downtime_prevented_hours ?? 18}h</strong>
          예방 추정 정지시간
        </span>
        <span>
          <strong>{report?.digitized_knowhow_count ?? 0}건</strong>
          디지털 노하우
        </span>
      </div>
      <div className="chart small">
        <ResponsiveContainer width="100%" height={170}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} interval={0} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Bar dataKey="count" fill="#0f766e" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="queue-chart">
        <ResponsiveContainer width="100%" height={88}>
          <AreaChart data={[{ x: "기준", y: 0 }, { x: "현재", y: report?.training_queue_count ?? 0 }]}>
            <Area dataKey="y" stroke="#2563eb" fill="#bfdbfe" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default App;
