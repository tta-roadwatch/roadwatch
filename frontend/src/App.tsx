import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider } from "./auth/AuthContext";
import { AppShell } from "./components/AppShell";
import { Dashboard } from "./pages/Dashboard";
import { Datasets } from "./pages/Datasets";
import { Normalization } from "./pages/Normalization";
import { Quality } from "./pages/Quality";
import { MapPage } from "./pages/MapPage";
import { CellDetail } from "./pages/CellDetail";
import { Comparison } from "./pages/Comparison";
import { Inspections } from "./pages/Inspections";
import { Standards } from "./pages/Standards";
import { Login } from "./pages/Login";

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
        {/* 로그인은 상단 메뉴 없이 단독으로 뜬다 */}
        <Route path="/login" element={<Login />} />

        <Route
          path="*"
          element={
            <AppShell>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/data" element={<Datasets />} />
                <Route path="/data/normalization" element={<Normalization />} />
                <Route path="/data/quality" element={<Quality />} />
                <Route path="/map" element={<MapPage />} />
                <Route path="/cells/:cellKey" element={<CellDetail />} />
                <Route
                  path="/cells/:cellKey/comparison"
                  element={<Comparison />}
                />
                <Route path="/inspections" element={<Inspections />} />
                <Route path="/standards" element={<Standards />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </AppShell>
          }
        />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
