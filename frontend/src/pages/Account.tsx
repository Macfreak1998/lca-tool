import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AuthApi } from "../api";
import { useAuth } from "../auth";

export function AccountPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState("");

  async function remove() {
    if (!confirm("Konto, Konfigurationen und eigene Datensätze unwiderruflich löschen?")) return;
    try {
      await AuthApi.deleteMe();
      await logout();
      navigate("/login");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Löschen fehlgeschlagen.");
    }
  }

  return (
    <div className="card max-w-xl space-y-4">
      <h1 className="text-xl font-semibold">Konto</h1>
      <p>
        <strong>{user?.email}</strong> · Rolle: {user?.role === "admin" ? "Administration" : "Nutzer"}
      </p>
      {error && <p className="text-sm text-red-700">{error}</p>}
      <button className="btn-secondary text-red-700" type="button" onClick={() => void remove()}>
        Konto vollständig löschen
      </button>
    </div>
  );
}
