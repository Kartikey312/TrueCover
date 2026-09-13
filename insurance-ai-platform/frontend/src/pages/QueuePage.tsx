import { useState } from "react";

import { useQueue } from "../api/queries";
import { QueueTable } from "../components/queue/QueueTable";
import { Card } from "../components/ui/Card";
import { ErrorState, Spinner } from "../components/ui/Feedback";
import { useAuth } from "../context/AuthContext";

type QueueView = "mine" | "unassigned";

export function QueuePage() {
  const { user } = useAuth();
  const [view, setView] = useState<QueueView>("mine");

  const { data: claims, isLoading, isError } = useQueue(view === "mine" ? user!.user_id : null);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">
            {view === "mine" ? "My queue" : "Unassigned intake queue"}
          </h1>
          <p className="text-sm text-slate-500">
            {view === "mine" ? "Claims assigned to you that are still open." : "Claims not yet assigned to an adjuster."}
          </p>
        </div>

        <div className="flex gap-2 rounded-md bg-slate-100 p-1 text-sm">
          <button
            className={`rounded px-3 py-1.5 font-medium transition ${view === "mine" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}
            onClick={() => setView("mine")}
          >
            My queue
          </button>
          <button
            className={`rounded px-3 py-1.5 font-medium transition ${view === "unassigned" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}
            onClick={() => setView("unassigned")}
          >
            Unassigned
          </button>
        </div>
      </div>

      <Card>
        {isLoading && <Spinner label="Loading queue…" />}
        {isError && <ErrorState message="Could not load the queue. Is the API running?" />}
        {claims && <QueueTable claims={claims} />}
      </Card>
    </div>
  );
}
