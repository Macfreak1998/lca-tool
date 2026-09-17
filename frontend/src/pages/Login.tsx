import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AuthApi, MetaApi } from "../api";
import { useAuth } from "../auth";

export function LoginPage() {
  const { refresh, user } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("admin@localhost");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [signup, setSignup] = useState(false);

  useEffect(() => {
    void MetaApi.public().then((info) => setSignup(info.public_signup));
  }, []);
  useEffect(() => {
    if (user) navigate("/");
  }, [user, navigate]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await AuthApi.login(email, password);
      await refresh();
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Anmeldung fehlgeschlagen.");
    }
  }

  return (
    <div className="mx-auto mt-16 max-w-md">
      <h1 className="mb-2 text-2xl font-semibold text-forest-800">Anmelden</h1>
      <p className="mb-6 text-sm text-slate-600">
        Web-Tool zur Abschätzung der Umweltwirkung biobasierter Kunststoffe.
      </p>
      <form className="card space-y-4" onSubmit={(event) => void onSubmit(event)}>
        {error && <p className="text-sm text-red-700">{error}</p>}
        <div>
          <label className="label">E-Mail</label>
          <input className="input" value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
        </div>
        <div>
          <label className="label">Passwort</label>
          <input
            className="input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            required
          />
        </div>
        <button className="btn w-full" type="submit">
          Anmelden
        </button>
        <div className="flex justify-between text-sm">
          <Link className="text-forest-700 underline" to="/passwort-vergessen">
            Passwort vergessen
          </Link>
          {signup && (
            <Link className="text-forest-700 underline" to="/registrieren">
              Konto anlegen
            </Link>
          )}
        </div>
      </form>
    </div>
  );
}
