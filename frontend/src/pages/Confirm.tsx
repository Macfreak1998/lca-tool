import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AuthApi } from "../api";

export function ConfirmPage() {
  const [params] = useSearchParams();
  const [status, setStatus] = useState("bestätige …");

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      setStatus("Der Link ist unvollständig.");
      return;
    }
    void AuthApi.confirm(token)
      .then(() => setStatus("E-Mail bestätigt. Sie können sich anmelden."))
      .catch((err: Error) => setStatus(err.message));
  }, [params]);

  return (
    <div className="mx-auto mt-16 max-w-md card">
      <p>{status}</p>
      <Link className="mt-4 inline-block text-forest-700 underline" to="/login">
        Zur Anmeldung
      </Link>
    </div>
  );
}
