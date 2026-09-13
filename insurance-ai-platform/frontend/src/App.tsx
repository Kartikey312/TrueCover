import { Route, Routes } from "react-router-dom";

import { Layout } from "./components/layout/Layout";
import { Spinner } from "./components/ui/Feedback";
import { useAuth } from "./context/AuthContext";
import { ClaimDetailPage } from "./pages/ClaimDetailPage";
import { LoginPage } from "./pages/LoginPage";
import { QueuePage } from "./pages/QueuePage";

export function App() {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner label="Loading…" />
      </div>
    );
  }

  if (!user) {
    return <LoginPage />;
  }

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<QueuePage />} />
        <Route path="/claims/:claimId" element={<ClaimDetailPage />} />
      </Routes>
    </Layout>
  );
}
