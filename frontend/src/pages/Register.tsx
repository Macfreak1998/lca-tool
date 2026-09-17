import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { AuthApi } from "../api";

export function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await AuthApi.register(email, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registrierung fehlgeschlagen.");
    }
  }

  if (done) {
    return (
      <div className="mx-auto mt-16 max-w-md card">
        <h1 className="mb-2 text-xl font-semibold">Bitte E-Mail bestätigen</h1>
        <p className="text-sm text-slate-600">
          Wir haben einen Bestätigungslink an {email} gesendet. Ohne Bestätigung ist kein Login möglich. Lokal ohne
          SMTP erscheint der Link in der Serverkonsole.
        </p>
        <Link className="mt-4 inline-block text-forest-700 underline" to="/login">
          Zur Anmeldung
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto mt-16 max-w-md">
      <h1 className="mb-4 text-2xl font-semibold text-forest-800">Konto anlegen</h1>
      <form className="card space-y-4" onSubmit={(event) => void onSubmit(event)}>
        {error && <p className="text-sm text-red-700">{error}</p>}
        <div>
          <label className="label">E-Mail</label>
          <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div>
          <label className="label">Passwort (mindestens 8 Zeichen)</label>
          <input
            className="input"
            type="password"
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>
        <button className="btn w-full" type="submit">
          Registrieren
        </button>
        <Link className="block text-center text-sm text-forest-700 underline" to="/login">
          Schon ein Konto?
        </Link>
      </form>
    </div>
  );
}
