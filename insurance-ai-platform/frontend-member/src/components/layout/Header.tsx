import { Link } from "react-router-dom";

import { Button } from "../ui/Button";
import { useMemberAuth } from "../../context/MemberContext";

export function Header() {
  const { member, logout } = useMemberAuth();

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
        <Link to="/" className="text-lg font-semibold text-slate-900">
          My Coverage
        </Link>

        {member && (
          <div className="flex items-center gap-3 text-sm text-slate-600">
            <span>
              {member.first_name} {member.last_name}
            </span>
            <Button variant="ghost" onClick={logout}>
              Sign out
            </Button>
          </div>
        )}
      </div>
    </header>
  );
}
