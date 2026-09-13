import type { ClaimDocumentRead } from "../../api/types";
import { formatDateTime } from "../../lib/format";
import { Card } from "../ui/Card";
import { EmptyState } from "../ui/Feedback";

export function ClaimDocumentsCard({ documents }: { documents: ClaimDocumentRead[] }) {
  return (
    <Card title="Documents you've submitted">
      {documents.length === 0 ? (
        <EmptyState message="No documents attached." />
      ) : (
        <ul className="divide-y divide-slate-100">
          {documents.map((doc) => (
            <li key={doc.document_id} className="py-2 text-sm">
              <div className="font-medium text-slate-800">{doc.file_name}</div>
              <div className="text-xs text-slate-500">Uploaded {formatDateTime(doc.uploaded_at)}</div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
