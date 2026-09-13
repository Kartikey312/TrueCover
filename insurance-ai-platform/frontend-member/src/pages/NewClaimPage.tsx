import { Link } from "react-router-dom";

import { NewClaimForm } from "../components/claims/NewClaimForm";
import { Card } from "../components/ui/Card";

export function NewClaimPage() {
  return (
    <div className="space-y-4">
      <Link to="/" className="text-sm font-medium text-blue-700 hover:underline">
        ← Back to my claims
      </Link>

      <div>
        <h1 className="text-xl font-semibold text-slate-900">File a new claim</h1>
        <p className="text-sm text-slate-500">
          Fill in what you know, attach your invoice, and we'll take it from there.
        </p>
      </div>

      <Card>
        <NewClaimForm />
      </Card>
    </div>
  );
}
