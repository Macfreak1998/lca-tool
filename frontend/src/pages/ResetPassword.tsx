import { FormEvent, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AuthApi } from "../api";

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const [password, setPassword] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const token = params.get("token") || "";
    try {
      await AuthApi.reset(token, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler");
    }
  }

  return (
    <div className="mx-auto mt-16 max-w-md card space-y-4">
      <h1 className="text-xl font-semibold">Neues Passwort</h1>
      {done ? (
        <Link className="text-forest-700 underline" to="/login">
          Anmelden
        </Link>
      ) : (
        <form className="space-y-4" onSubmit={(event) => void onSubmit(event)}>
          {error && <p className="text-sm text-red-700">{error}</p>}
          <input
            className="input"
            type="password"
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Neues Passwort"
            required
          />
          <button className="btn" type="submit">
            Speichern
          </button>
        </form>
      )}
    </div>
  );
}
