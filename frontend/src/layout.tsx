import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "./auth";

function linkClass({ isActive }: { isActive: boolean }) {
  return `rounded-md px-3 py-1.5 text-sm ${isActive ? "bg-white/15 font-semibold" : "hover:bg-white/10"}`;
}

export function AppLayout() {
  const { user, logout } = useAuth();
  return (
    <div className="min-h-screen">
      <header className="bg-forest-700 text-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-4 py-3">
          <strong className="mr-4 text-lg">LCA-Tool</strong>
          <NavLink to="/" className={linkClass} end>
            Rechnen
          </NavLink>
          <NavLink to="/konfigurationen" className={linkClass}>
            Konfigurationen
          </NavLink>
          <NavLink to="/vergleich" className={linkClass}>
            Vergleich
          </NavLink>
          <NavLink to="/eigene-datensaetze" className={linkClass}>
            Eigene Datensätze
          </NavLink>
          {user?.role === "admin" && (
            <NavLink to="/admin" className={linkClass}>
              Administration
            </NavLink>
          )}
          <div className="ml-auto flex items-center gap-3 text-sm">
            <NavLink to="/konto" className={linkClass}>
              {user?.email}
            </NavLink>
            <button type="button" className="text-sm underline" onClick={() => void logout()}>
              Abmelden
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}

export function AdminLayout() {
  return (
    <div className="grid gap-6 md:grid-cols-[220px_1fr]">
      <aside className="card h-fit space-y-1 p-3">
        <NavLink to="/admin" className={adminLink} end>
          Übersicht
        </NavLink>
        <NavLink to="/admin/archiv" className={adminLink}>
          Archiv und Import
        </NavLink>
        <NavLink to="/admin/kategorien" className={adminLink}>
          Kategorien
        </NavLink>
        <NavLink to="/admin/endprodukte" className={adminLink}>
          Endprodukte
        </NavLink>
        <NavLink to="/admin/ketten" className={adminLink}>
          Ketten
        </NavLink>
        <NavLink to="/admin/vorschlaege" className={adminLink}>
          Vorschläge
        </NavLink>
        <NavLink to="/admin/nutzer" className={adminLink}>
          Nutzer
        </NavLink>
      </aside>
      <div>
        <Outlet />
      </div>
    </div>
  );
}

function adminLink({ isActive }: { isActive: boolean }) {
  return `block rounded-md px-3 py-2 text-sm ${isActive ? "bg-forest-100 font-semibold text-forest-800" : "hover:bg-slate-50"}`;
}
