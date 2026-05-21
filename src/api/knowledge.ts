import type { KnowledgeDocumentDetail, KnowledgeDocumentSummary } from '../types';

export type KnowledgeDocumentsResponse = {
  data: KnowledgeDocumentSummary[];
};

export type KnowledgeDocumentResponse = {
  data: KnowledgeDocumentDetail;
};

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000';

function getApiBaseUrl() {
  return (import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL).replace(/\/$/, '');
}

export async function fetchKnowledgeDocuments(documentType = 'manual', signal?: AbortSignal): Promise<KnowledgeDocumentsResponse> {
  const params = new URLSearchParams({ documentType });
  const response = await fetch(`${getApiBaseUrl()}/api/v1/knowledge/documents?${params}`, { signal });

  if (!response.ok) {
    throw new Error(`Knowledge documents API request failed: ${response.status}`);
  }

  return response.json() as Promise<KnowledgeDocumentsResponse>;
}

export async function fetchKnowledgeDocument(documentId: number, signal?: AbortSignal): Promise<KnowledgeDocumentResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/knowledge/documents/${documentId}`, { signal });

  if (!response.ok) {
    throw new Error(`Knowledge document API request failed: ${response.status}`);
  }

  return response.json() as Promise<KnowledgeDocumentResponse>;
}
