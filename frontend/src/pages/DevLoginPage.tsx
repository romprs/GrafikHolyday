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
    <div style={{ maxWidth: 480, margin: "4rem auto", fontFamily: "sans-serif" }}>
      <h1>Планирование отпусков</h1>

      {devUsers.length > 0 && (
        <>
          <p>Dev-режим входа — выберите тестового пользователя:</p>
          <ul style={{ listStyle: "none", padding: 0 }}>
            {devUsers.map((u) => (
              <li key={u.id} style={{ marginBottom: 8 }}>
                <button
                  onClick={() => loginAs(u.id)}
                  style={{ width: "100%", textAlign: "left", padding: "8px 12px" }}
                >
                  {u.full_name} — {u.email}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      <details open={devUsers.length === 0} style={{ marginTop: devUsers.length > 0 ? 24 : 0 }}>
        <summary style={{ cursor: "pointer", color: "#888" }}>Аварийный вход HR-admin</summary>
        <form
          onSubmit={handleFallbackSubmit}
          style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8, maxWidth: 300 }}
        >
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <input
            type="password"
            placeholder="Пароль"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <button type="submit" disabled={submitting}>
            Войти
          </button>
          {error && (
            <p style={{ color: "crimson", margin: 0 }}>{error}</p>
          )}
        </form>
      </details>
    </div>
  );
}

export function roleLabel(role: string): string {
  return roleLabelRu[role] ?? role;
}
