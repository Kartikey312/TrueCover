import { Route, Routes } from "react-router-dom";

import { Layout } from "./components/layout/Layout";
import { Spinner } from "./components/ui/Feedback";
import { useMemberAuth } from "./context/MemberContext";
import { ClaimStatusPage } from "./pages/ClaimStatusPage";
import { LoginPage } from "./pages/LoginPage";
import { MyClaimsPage } from "./pages/MyClaimsPage";
import { NewClaimPage } from "./pages/NewClaimPage";

export function App() {
  const { member, isLoading } = useMemberAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner label="Loading…" />
      </div>
    );
  }

  if (!member) {
    return <LoginPage />;
  }

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<MyClaimsPage />} />
        <Route path="/claims/new" element={<NewClaimPage />} />
        <Route path="/claims/:claimId" element={<ClaimStatusPage />} />
      </Routes>
    </Layout>
  );
}
