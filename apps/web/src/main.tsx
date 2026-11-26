import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AdminJobsPage } from "@/pages/admin/AdminJobsPage";
import { AdminOverviewPage } from "@/pages/admin/AdminOverviewPage";
import { AdminProvidersPage } from "@/pages/admin/AdminProvidersPage";
import { AdminQualityPage } from "@/pages/admin/AdminQualityPage";
import { AdminSettingsPage } from "@/pages/admin/AdminSettingsPage";
import { AdminTemplatesPage } from "@/pages/admin/AdminTemplatesPage";
import { AdminUsersPage } from "@/pages/admin/AdminUsersPage";
import { DocumentPage } from "@/pages/DocumentPage";
import { GeneratePage } from "@/pages/GeneratePage";
import { HomePage } from "@/pages/HomePage";
import { LoginPage } from "@/pages/LoginPage";
import "@/styles/index.css";

const queryClient = new QueryClient();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/generate" element={<GeneratePage />} />
          <Route path="/documents/:documentId" element={<DocumentPage />} />
          <Route path="/admin" element={<AdminOverviewPage />} />
          <Route path="/admin/templates" element={<AdminTemplatesPage />} />
          <Route path="/admin/providers" element={<AdminProvidersPage />} />
          <Route path="/admin/quality" element={<AdminQualityPage />} />
          <Route path="/admin/users" element={<AdminUsersPage />} />
          <Route path="/admin/jobs" element={<AdminJobsPage />} />
          <Route path="/admin/settings" element={<AdminSettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
