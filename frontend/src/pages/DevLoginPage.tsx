import { useState } from "react";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";

const roleLabelRu: Record<string, string> = {
  employee: "Сотрудник",
  manager: "Руководитель",
  hr_admin: "HR / администратор",
};

export function DevLoginPage() {
  const { devUsers, loginAs, loginAsFallback } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleFallbackSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await loginAsFallback(email, password);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось войти");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
      <div className="panel" style={{ width: "100%", maxWidth: 400 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 18 }}>
          <span style={{ width: 9, height: 9, borderRadius: "50%", background: "var(--accent)" }} />
          <h3 style={{ margin: 0 }}>Планирование отпусков</h3>
        </div>

        {devUsers.length > 0 && (
          <>
            <p className="hint" style={{ marginBottom: 10 }}>Dev-режим входа — выберите тестового пользователя:</p>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 20 }}>
              {devUsers.map((u) => (
                <button
                  key={u.id}
                  type="button"
                  className="btn-outline"
                  onClick={() => loginAs(u.id)}
                  style={{ textAlign: "left" }}
                >
                  {u.full_name} — {u.email}
                </button>
              ))}
            </div>
          </>
        )}

        <details open={devUsers.length === 0}>
          <summary style={{ cursor: "pointer", color: "var(--ink-mute)", fontSize: 13.5 }}>Аварийный вход HR-admin</summary>
          <form onSubmit={handleFallbackSubmit} style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
            <input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            <input type="password" placeholder="Пароль" value={password} onChange={(e) => setPassword(e.target.value)} required />
            <button type="submit" className="btn-primary" disabled={submitting}>
              Войти
            </button>
            {error && <p className="error-text" style={{ margin: 0 }}>{error}</p>}
          </form>
        </details>
      </div>
    </div>
  );
}

export function roleLabel(role: string): string {
  return roleLabelRu[role] ?? role;
}
