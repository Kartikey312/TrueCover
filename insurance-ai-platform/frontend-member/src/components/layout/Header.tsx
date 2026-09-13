import { Link } from "react-router-dom";

import { useMembers } from "../../api/queries";
import { useMemberIdentity } from "../../context/MemberContext";

export function Header() {
  const { memberId, setMemberId } = useMemberIdentity();
  const { data: members, isLoading } = useMembers();

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
        <Link to="/" className="text-lg font-semibold text-slate-900">
          My Coverage
        </Link>

        <label className="flex items-center gap-2 text-sm text-slate-600">
          Signed in as
          <select
            className="rounded-md border-slate-300 bg-white py-1.5 pl-3 pr-8 text-sm text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-600"
            value={memberId ?? ""}
            onChange={(event) => setMemberId(event.target.value || null)}
            disabled={isLoading}
          >
            <option value="">Select a member…</option>
            {members?.map((member) => (
              <option key={member.member_id} value={member.member_id}>
                {member.first_name} {member.last_name}
              </option>
            ))}
          </select>
        </label>
      </div>
    </header>
  );
}
