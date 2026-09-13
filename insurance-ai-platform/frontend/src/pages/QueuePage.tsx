import { useQueue } from "../api/queries";
import { QueueTable } from "../components/queue/QueueTable";
import { Card } from "../components/ui/Card";
import { ErrorState, Spinner } from "../components/ui/Feedback";
import { useAdjusterIdentity } from "../context/AdjusterContext";

export function QueuePage() {
  const { adjusterId } = useAdjusterIdentity();
  const { data: claims, isLoading, isError } = useQueue(adjusterId);

  const title = adjusterId ? "My queue" : "Unassigned intake queue";
  const subtitle = adjusterId
    ? "Claims assigned to you that are still open."
    : "Claims not yet assigned to an adjuster.";

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
        <p className="text-sm text-slate-500">{subtitle}</p>
      </div>

      <Card>
        {isLoading && <Spinner label="Loading queue…" />}
        {isError && <ErrorState message="Could not load the queue. Is the API running?" />}
        {claims && <QueueTable claims={claims} />}
      </Card>
    </div>
  );
}
