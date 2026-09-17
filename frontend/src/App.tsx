import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import { AdminLayout, AppLayout } from "./layout";
import { AccountPage } from "./pages/Account";
import { ComparePage } from "./pages/Compare";
import { ConfigurationsPage } from "./pages/Configurations";
import { ConfirmPage } from "./pages/Confirm";
import { ForgotPage } from "./pages/Forgot";
import { LoginPage } from "./pages/Login";
import { RechnenPage } from "./pages/Rechnen";
import { RegisterPage } from "./pages/Register";
import { ResetPasswordPage } from "./pages/ResetPassword";
import { UserDatasetsPage } from "./pages/UserDatasets";
import { AdminHomePage } from "./pages/admin/AdminHome";
import { ArchivePage } from "./pages/admin/Archive";
import { ChainEditorPage } from "./pages/admin/ChainEditor";
import { ChainsPage } from "./pages/admin/Chains";
import { EndProductsPage } from "./pages/admin/EndProducts";
import { ProposalsPage } from "./pages/admin/Proposals";
import { RolesPage } from "./pages/admin/Roles";
import { UsersPage } from "./pages/admin/Users";

function Guard({ children, admin }: { children: ReactNode; admin?: boolean }) {
  const { user, loading } = useAuth();
  if (loading) return <p className="p-8">Laden …</p>;
  if (!user) return <Navigate to="/login" replace />;
  if (admin && user.role !== "admin") return <Navigate to="/" replace />;
  return children;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/registrieren" element={<RegisterPage />} />
      <Route path="/confirm" element={<ConfirmPage />} />
      <Route path="/passwort-vergessen" element={<ForgotPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route
        element={
          <Guard>
            <AppLayout />
          </Guard>
        }
      >
        <Route path="/" element={<RechnenPage />} />
        <Route path="/konfigurationen" element={<ConfigurationsPage />} />
        <Route path="/vergleich" element={<ComparePage />} />
        <Route path="/eigene-datensaetze" element={<UserDatasetsPage />} />
        <Route path="/konto" element={<AccountPage />} />
        <Route
          path="/admin"
          element={
            <Guard admin>
              <AdminLayout />
            </Guard>
          }
        >
          <Route index element={<AdminHomePage />} />
          <Route path="archiv" element={<ArchivePage />} />
          <Route path="kategorien" element={<RolesPage />} />
          <Route path="endprodukte" element={<EndProductsPage />} />
          <Route path="ketten" element={<ChainsPage />} />
          <Route path="ketten/:id" element={<ChainEditorPage />} />
          <Route path="vorschlaege" element={<ProposalsPage />} />
          <Route path="nutzer" element={<UsersPage />} />
        </Route>
      </Route>
    </Routes>
  );
}
