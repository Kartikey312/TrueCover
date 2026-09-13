import { useState } from "react";

import { api } from "../../api/client";
import type { ClaimDocumentRead } from "../../api/types";
import { formatDateTime, titleCase } from "../../lib/format";
import { Card } from "../ui/Card";
import { EmptyState } from "../ui/Feedback";

function isPreviewableImage(mimeType: string | null): boolean {
  return !!mimeType && mimeType.startsWith("image/");
}

function isPreviewableText(mimeType: string | null): boolean {
  return !!mimeType && (mimeType.startsWith("text/") || mimeType === "application/json");
}

function isPdf(mimeType: string | null): boolean {
  return mimeType === "application/pdf";
}

function formatBytes(size: number | null): string {
  if (size === null) return "";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export function DocumentViewer({ claimId, documents }: { claimId: string; documents: ClaimDocumentRead[] }) {
  const [selectedId, setSelectedId] = useState<string | null>(documents[0]?.document_id ?? null);
  const selected = documents.find((doc) => doc.document_id === selectedId) ?? null;

  if (documents.length === 0) {
    return (
      <Card title="Documents">
        <EmptyState message="No documents have been uploaded for this claim." />
      </Card>
    );
  }

  const fileUrl = selected ? api.fileUrl(`/claims/${claimId}/documents/${selected.document_id}/file`) : null;

  return (
    <Card title="Documents">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <ul className="space-y-1 md:col-span-1">
          {documents.map((doc) => (
            <li key={doc.document_id}>
              <button
                onClick={() => setSelectedId(doc.document_id)}
                className={`w-full rounded-md px-2 py-1.5 text-left text-sm ${
                  doc.document_id === selectedId ? "bg-emerald-50 text-emerald-800" : "hover:bg-slate-50"
                }`}
              >
                <div className="truncate font-medium">{doc.file_name}</div>
                <div className="text-xs text-slate-500">
                  {titleCase(doc.document_type)} · {formatBytes(doc.file_size_bytes)}
                </div>
              </button>
            </li>
          ))}
        </ul>

        <div className="md:col-span-2">
          {selected && fileUrl && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs text-slate-500">
                <span>Uploaded {formatDateTime(selected.uploaded_at)}</span>
                <a href={fileUrl} target="_blank" rel="noreferrer" className="font-medium text-emerald-700 hover:underline">
                  Open in new tab
                </a>
              </div>

              <div className="overflow-hidden rounded-md border border-slate-200 bg-slate-50">
                {isPreviewableImage(selected.mime_type) && (
                  <img src={fileUrl} alt={selected.file_name} className="max-h-96 w-full object-contain" />
                )}
                {isPdf(selected.mime_type) && <iframe title={selected.file_name} src={fileUrl} className="h-96 w-full" />}
                {isPreviewableText(selected.mime_type) && (
                  <iframe title={selected.file_name} src={fileUrl} className="h-64 w-full bg-white" />
                )}
                {!isPreviewableImage(selected.mime_type) &&
                  !isPdf(selected.mime_type) &&
                  !isPreviewableText(selected.mime_type) && (
                    <div className="p-6 text-center text-sm text-slate-500">
                      No inline preview for this file type ({selected.mime_type ?? "unknown"}). Use "Open in new tab"
                      to download it.
                    </div>
                  )}
              </div>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}
