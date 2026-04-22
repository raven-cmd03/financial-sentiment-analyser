import { Routes, Route, useLocation } from "react-router-dom";
import { AppProvider } from "@/context/AppContext";
import ThemeProvider from "@/components/layout/ThemeProvider";
import AppShell from "@/components/layout/AppShell";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import DashboardPage from "@/pages/DashboardPage";
import CompanyDetailPage from "@/pages/CompanyDetailPage";
import TrendAnalysisPage from "@/pages/TrendAnalysisPage";
import ChatPage from "@/pages/ChatPage";
import ModelManagementPage from "@/pages/ModelManagementPage";
import OnboardingPage from "@/pages/OnboardingPage";

function AppRoutes() {
  const location = useLocation();
  const isOnboarding = location.pathname === "/onboarding";

  const routes = (
    <Routes>
      <Route path="/" element={<DashboardPage />} />
      <Route path="/company/:ticker" element={<CompanyDetailPage />} />
      <Route path="/trends" element={<TrendAnalysisPage />} />
      <Route path="/chat" element={<ChatPage />} />
      <Route path="/models" element={<ModelManagementPage />} />
      <Route path="/onboarding" element={<OnboardingPage />} />
    </Routes>
  );

  if (isOnboarding) return routes;
  return <AppShell>{routes}</AppShell>;
}

function App() {
  return (
    <ThemeProvider>
      <TooltipProvider delayDuration={200}>
        <AppProvider>
          <AppRoutes />
          <Toaster richColors position="top-right" />
        </AppProvider>
      </TooltipProvider>
    </ThemeProvider>
  );
}

export default App;
