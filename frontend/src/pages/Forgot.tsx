import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { AuthApi } from "../api";

export function ForgotPage() {
  const [email, setEmail] = useState("");
  const [done, setDone] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    await AuthApi.requestReset(email);
    setDone(true);
  }

  return (
    <div className="mx-auto mt-16 max-w-md">
      <h1 className="mb-4 text-2xl font-semibold text-forest-800">Passwort zurücksetzen</h1>
      <form className="card space-y-4" onSubmit={(event) => void onSubmit(event)}>
        {done ? (
          <p className="text-sm">Wenn ein Konto existiert, wurde ein Link per E-Mail (oder Serverlog) gesendet.</p>
        ) : (
          <>
            <div>
              <label className="label">E-Mail</label>
              <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <button className="btn w-full" type="submit">
              Link senden
            </button>
          </>
        )}
        <Link className="block text-center text-sm text-forest-700 underline" to="/login">
          Zurück
        </Link>
      </form>
    </div>
  );
}
