import { Link } from "react-router-dom";

import { useAdjusters } from "../../api/queries";
import { useAdjusterIdentity } from "../../context/AdjusterContext";

export function Header() {
  const { adjusterId, setAdjusterId } = useAdjusterIdentity();
  const { data: adjusters, isLoading } = useAdjusters();

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link to="/" className="text-lg font-semibold text-slate-900">
          Adjuster Console
        </Link>

        <label className="flex items-center gap-2 text-sm text-slate-600">
          Acting as
          <select
            className="rounded-md border-slate-300 bg-white py-1.5 pl-3 pr-8 text-sm text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 focus:outline-none focus:ring-2 focus:ring-emerald-600"
            value={adjusterId ?? ""}
            onChange={(event) => setAdjusterId(event.target.value || null)}
            disabled={isLoading}
          >
            <option value="">Unassigned queue (no adjuster)</option>
            {adjusters?.map((adjuster) => (
              <option key={adjuster.user_id} value={adjuster.user_id}>
                {adjuster.full_name}
              </option>
            ))}
          </select>
        </label>
      </div>
    </header>
  );
}
