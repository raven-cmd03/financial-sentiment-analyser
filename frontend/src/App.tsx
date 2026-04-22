import { Routes, Route } from "react-router-dom";
import { AppProvider } from "@/context/AppContext";
import DashboardPage from "@/pages/DashboardPage";
import CompanyDetailPage from "@/pages/CompanyDetailPage";
import TrendAnalysisPage from "@/pages/TrendAnalysisPage";
import ChatPage from "@/pages/ChatPage";
import ModelManagementPage from "@/pages/ModelManagementPage";
import OnboardingPage from "@/pages/OnboardingPage";

function App() {
  return (
    <AppProvider>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/company/:ticker" element={<CompanyDetailPage />} />
        <Route path="/trends" element={<TrendAnalysisPage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/models" element={<ModelManagementPage />} />
        <Route path="/onboarding" element={<OnboardingPage />} />
      </Routes>
    </AppProvider>
  );
}

export default App;
