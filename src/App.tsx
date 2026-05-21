import { useCallback, useEffect, useState } from 'react';
import type { Equipment, PageId, WorkOrder } from './types';
import { fetchDashboard, type DashboardSummary } from './api/dashboard';
import { subscribeRealtime } from './api/realtime';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { KakaoModal } from './components/KakaoModal';
import { Dashboard } from './pages/Dashboard';
import { EquipmentDetail } from './pages/EquipmentDetail';
import { WorkOrder as WorkOrderPage } from './pages/WorkOrder';
import { WorkOrderManagement } from './pages/WorkOrderManagement';
import { Manuals } from './pages/Manuals';
import { ResultForm } from './pages/ResultForm';
import { KnowHowReport } from './pages/KnowHowReport';

const PAGE_IDS: PageId[] = ['dashboard', 'detail', 'workorder', 'workorders', 'manuals', 'result', 'report'];

function getInitialPage(): PageId {
  try {
    const saved = localStorage.getItem('gj_page') as PageId | null;
    return saved && PAGE_IDS.includes(saved) ? saved : 'dashboard';
  } catch {
    return 'dashboard';
  }
}

function getInitialEquipmentId(): string | null {
  try {
    return localStorage.getItem('gj_eq');
  } catch {
    return null;
  }
}

function App() {
  const [page, setPage] = useState<PageId>(() => getInitialPage());
  const [selectedEquipmentId] = useState<string | null>(() => getInitialEquipmentId());
  const [selectedEq, setSelectedEq] = useState<Equipment | null>(null);
  const [selectedWorkOrderId, setSelectedWorkOrderId] = useState<number | null>(null);
  const [selectedManualId, setSelectedManualId] = useState<number | null>(null);
  const [alertCount, setAlertCount] = useState(0);
  const [kakaoOrder, setKakaoOrder] = useState<WorkOrder | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    fetchDashboard(controller.signal)
      .then(response => {
        const { summary, equipment } = response.data;
        const restored = selectedEquipmentId
          ? equipment.find(item => String(item.id) === selectedEquipmentId)
          : null;

        setAlertCount(summary.dangerCount + summary.warnCount);
        setSelectedEq(prev => prev ?? restored ?? null);
      })
      .catch(error => {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return;
        }
        console.error('Failed to load app equipment state', error);
      });

    return () => controller.abort();
  }, [selectedEquipmentId]);

  useEffect(() => {
    return subscribeRealtime(event => {
      const { summary, equipment } = event.dashboard;

      setAlertCount(summary.dangerCount + summary.warnCount);
      setSelectedEq(prev => {
        if (!prev) return prev;
        return equipment.find(item => item.id === prev.id) ?? prev;
      });
    });
  }, []);

  function navigate(target: PageId, eq?: Equipment) {
    if (eq) setSelectedEq(eq);
    setPage(target);
    try {
      localStorage.setItem('gj_page', target);
      if (eq) localStorage.setItem('gj_eq', String(eq.id));
    } catch { /* ignore */ }
  }

  function handleSelectEquipment(eq: Equipment, targetPage?: PageId) {
    setSelectedEq(eq);
    navigate(targetPage ?? 'detail', eq);
  }

  const handleDashboardSummaryChange = useCallback((summary: DashboardSummary) => {
    setAlertCount(summary.dangerCount + summary.warnCount);
  }, []);

  const handleChangeEquipment = useCallback((eq: Equipment) => {
    setSelectedEq(eq);
  }, []);

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        currentPage={page}
        onNavigate={(id) => navigate(id)}
        alerts={alertCount}
      />

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <Header page={page} selectedEq={selectedEq} onBack={() => navigate('dashboard')} />

        <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-7 py-5">
          {page === 'dashboard' && (
            <Dashboard onSelectEquipment={handleSelectEquipment} onSummaryChange={handleDashboardSummaryChange} />
          )}
          {page === 'detail' && (
            <EquipmentDetail
              eq={selectedEq}
              onNavigate={(p, eq) => navigate(p, eq)}
              onChangeEquipment={handleChangeEquipment}
            />
          )}
          {page === 'workorder' && (
            selectedEq ? (
              <WorkOrderPage
                eq={selectedEq}
                onSendKakao={(order) => setKakaoOrder(order)}
                onOpenManual={(sourceRef) => {
                  setSelectedManualId(sourceRef.documentId);
                  navigate('manuals');
                }}
                onGenerated={(order) => {
                  setSelectedWorkOrderId(order.id);
                  navigate('workorders');
                }}
                onNavigateResult={() => navigate('result', selectedEq)}
              />
            ) : (
              <div className="rounded-md border border-border bg-bg-card px-4 py-3 text-sm text-text-secondary">
                작업지시서를 생성할 설비를 먼저 선택해 주세요.
              </div>
            )
          )}
          {page === 'workorders' && (
            <WorkOrderManagement
              selectedWorkOrderId={selectedWorkOrderId}
              onSelectWorkOrder={setSelectedWorkOrderId}
              onCreateNew={() => navigate('workorder', selectedEq ?? undefined)}
              onOpenManual={(sourceRef) => {
                setSelectedManualId(sourceRef.documentId);
                navigate('manuals');
              }}
            />
          )}
          {page === 'manuals' && (
            <Manuals
              selectedDocumentId={selectedManualId}
              onSelectDocument={setSelectedManualId}
            />
          )}
          {page === 'result' && (
            selectedEq ? (
              <ResultForm eq={selectedEq} />
            ) : (
              <div className="rounded-md border border-border bg-bg-card px-4 py-3 text-sm text-text-secondary">
                정비 결과를 입력할 설비를 먼저 선택해 주세요.
              </div>
            )
          )}
          {page === 'report' && <KnowHowReport />}
        </div>
      </div>

      {kakaoOrder && (
        <KakaoModal order={kakaoOrder} onClose={() => setKakaoOrder(null)} />
      )}
    </div>
  );
}

export default App;
