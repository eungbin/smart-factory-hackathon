import { useEffect, useState } from 'react';
import { fetchKnowledgeDocument, fetchKnowledgeDocuments } from '../api/knowledge';
import type { KnowledgeDocumentDetail, KnowledgeDocumentSummary } from '../types';
import { buttonClass, cn, ui } from '../utils/styles';

type Props = {
  selectedDocumentId: number | null;
  onSelectDocument: (documentId: number) => void;
};

function formatMeta(document: KnowledgeDocumentSummary) {
  return [
    document.sourceLabel,
    document.fileName,
    document.uploadedAt,
  ].filter(Boolean).join(' · ');
}

function chunkSection(chunk: KnowledgeDocumentDetail['chunks'][number]) {
  const section = chunk.metadata.section;
  return typeof section === 'string' && section ? section : `#${chunk.chunkNo}`;
}

export function Manuals({ selectedDocumentId, onSelectDocument }: Props) {
  const [documents, setDocuments] = useState<KnowledgeDocumentSummary[]>([]);
  const [detail, setDetail] = useState<KnowledgeDocumentDetail | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    fetchKnowledgeDocuments('manual', controller.signal)
      .then(response => {
        setDocuments(response.data);
        setLoadError(null);
        if (!selectedDocumentId && response.data[0]) {
          onSelectDocument(response.data[0].documentId);
        }
      })
      .catch(error => {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return;
        }
        console.error('Failed to load manuals', error);
        setLoadError('메뉴얼 목록을 불러오지 못했습니다.');
      })
      .finally(() => setLoadingList(false));

    return () => controller.abort();
  }, [onSelectDocument, selectedDocumentId]);

  useEffect(() => {
    if (!selectedDocumentId) {
      return;
    }

    const controller = new AbortController();

    fetchKnowledgeDocument(selectedDocumentId, controller.signal)
      .then(response => {
        setDetail(response.data);
        setLoadError(null);
      })
      .catch(error => {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return;
        }
        console.error('Failed to load manual detail', error);
        setLoadError('메뉴얼 상세를 불러오지 못했습니다.');
      });

    return () => controller.abort();
  }, [selectedDocumentId]);

  const showingSelectedDetail = Boolean(selectedDocumentId && detail?.documentId === selectedDocumentId);

  if (loadingList) {
    return <div className={cn(ui.card, 'px-5 py-4 text-sm text-text-secondary')}>메뉴얼 목록을 불러오는 중입니다.</div>;
  }

  if (loadError) {
    return (
      <div className="rounded-md border border-red-500/25 bg-red-500/8 px-4 py-3 text-sm text-red-300">
        {loadError}
      </div>
    );
  }

  if (documents.length === 0) {
    return <div className={cn(ui.card, 'px-5 py-4 text-sm text-text-secondary')}>등록된 메뉴얼이 없습니다.</div>;
  }

  return (
    <div className="grid animate-fade-in grid-cols-[320px_minmax(0,1fr)] gap-4">
      <div className={cn(ui.card, 'p-0')}>
        <div className="border-b border-border px-4 py-3">
          <div className="text-[13px] font-semibold text-text-secondary">메뉴얼 목록</div>
          <div className="mt-0.5 text-[11px] text-text-muted">{documents.length}개 문서</div>
        </div>
        <div className="flex max-h-[calc(100vh-190px)] flex-col overflow-y-auto">
          {documents.map(document => {
            const selected = document.documentId === selectedDocumentId;
            return (
              <button
                key={document.documentId}
                type="button"
                className={cn(
                  'border-b border-border bg-transparent px-4 py-3 text-left transition-colors hover:bg-bg-card-hover',
                  selected && 'bg-blue-500/10',
                )}
                onClick={() => onSelectDocument(document.documentId)}
              >
                <div className={cn('text-[13px] font-semibold', selected ? 'text-blue-400' : 'text-text-primary')}>
                  {document.title}
                </div>
                <div className="mt-1 line-clamp-2 text-[11px] leading-[1.45] text-text-muted">
                  {formatMeta(document)}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      <div className={ui.card}>
        {!showingSelectedDetail && <div className="text-sm text-text-secondary">메뉴얼 상세를 불러오는 중입니다.</div>}
        {showingSelectedDetail && detail && (
          <div className="flex flex-col gap-4">
            <div className="flex items-start justify-between gap-4 border-b border-border pb-4">
              <div>
                <div className="text-lg font-bold text-text-primary">{detail.title}</div>
                <div className="mt-1 text-xs text-text-muted">{formatMeta(detail)}</div>
              </div>
              <span className={ui.tag}>{detail.documentType}</span>
            </div>

            <div className="flex flex-col">
              {detail.chunks.map(chunk => (
                <div key={chunk.chunkId} className="border-b border-border py-4 first:pt-0 last:border-b-0 last:pb-0">
                  <div className="mb-2 flex items-center gap-2">
                    <span className={cn(ui.tag, 'border-cyan-500/20 bg-cyan-500/10 text-cyan-300')}>{chunkSection(chunk)}</span>
                    {chunk.heading && <span className="text-[13px] font-semibold text-text-primary">{chunk.heading}</span>}
                  </div>
                  <p className="whitespace-pre-wrap text-[13px] leading-[1.7] text-text-secondary">{chunk.body}</p>
                </div>
              ))}
            </div>

            {detail.fileUri && (
              <div className="flex justify-end">
                <a className={buttonClass('secondary', 'sm')} href={detail.fileUri}>
                  원본 URI 열기
                </a>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
