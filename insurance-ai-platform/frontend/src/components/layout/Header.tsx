import { Link } from "react-router-dom";

import { Button } from "../ui/Button";
import { useAuth } from "../../context/AuthContext";

export function Header() {
  const { user, logout } = useAuth();

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link to="/" className="text-lg font-semibold text-slate-900">
          Adjuster Console
        </Link>

        {user && (
          <div className="flex items-center gap-3 text-sm text-slate-600">
            <span>
              {user.full_name} <span className="text-slate-400">({user.role.replace(/_/g, " ")})</span>
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
