import { BrowserRouter, Route, Routes } from "react-router-dom";
import AppLayout from "@/layout/AppLayout";

import DashboardPage from "@/pages/DashboardPage";
import CustomersPage from "@/pages/CustomersPage";
import SegmentsPage from "@/pages/SegmentsPage";
import CampaignsPage from "@/pages/CampaignsPage";

  function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/customers" element={<CustomersPage />} />
          <Route path="/segments" element={<SegmentsPage />} />
          <Route path="/campaigns" element={<CampaignsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;