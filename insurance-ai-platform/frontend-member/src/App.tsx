import { Route, Routes } from "react-router-dom";

import { Layout } from "./components/layout/Layout";
import { ClaimStatusPage } from "./pages/ClaimStatusPage";
import { MyClaimsPage } from "./pages/MyClaimsPage";
import { NewClaimPage } from "./pages/NewClaimPage";

export function App() {
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
