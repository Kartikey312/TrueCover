import { useState, type FormEvent } from "react";

import { ApiError } from "../api/client";
import { Button } from "../components/ui/Button";
import { ErrorState } from "../components/ui/Feedback";
import { useMemberAuth } from "../context/MemberContext";

export function LoginPage() {
  const { login } = useMemberAuth();
  const [memberNumber, setMemberNumber] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(memberNumber, dateOfBirth);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong signing in.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm rounded-lg bg-white p-8 shadow-sm ring-1 ring-slate-200">
        <h1 className="mb-1 text-lg font-semibold text-slate-900">My Coverage</h1>
        <p className="mb-6 text-sm text-slate-500">
          Sign in with your member number and date of birth.
        </p>

        <form className="space-y-4" onSubmit={handleSubmit}>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Member number</span>
            <input
              type="text"
              required
              autoFocus
              placeholder="MBR-0001"
              value={memberNumber}
              onChange={(event) => setMemberNumber(event.target.value)}
              className="w-full rounded-md border-slate-300 shadow-sm ring-1 ring-inset ring-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-600"
            />
          </label>

          <label className="block text-sm">
            <span className="mb-1 block font-medium text-slate-700">Date of birth</span>
            <input
              type="date"
              required
              value={dateOfBirth}
              onChange={(event) => setDateOfBirth(event.target.value)}
              className="w-full rounded-md border-slate-300 shadow-sm ring-1 ring-inset ring-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-600"
            />
          </label>

          {error && <ErrorState message={error} />}

          <Button type="submit" variant="primary" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      </div>
    </div>
  );
}
