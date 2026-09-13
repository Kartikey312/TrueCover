import { Route, Routes } from "react-router-dom";

import { Layout } from "./components/layout/Layout";
import { ClaimDetailPage } from "./pages/ClaimDetailPage";
import { QueuePage } from "./pages/QueuePage";

export function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<QueuePage />} />
        <Route path="/claims/:claimId" element={<ClaimDetailPage />} />
      </Routes>
    </Layout>
  );
}
