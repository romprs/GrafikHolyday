import { useAuth } from "../auth/AuthContext";

const roleLabelRu: Record<string, string> = {
  employee: "Сотрудник",
  manager: "Руководитель",
  hr_admin: "HR / администратор",
};

export function DevLoginPage() {
  const { devUsers, loginAs } = useAuth();

  return (
    <div style={{ maxWidth: 480, margin: "4rem auto", fontFamily: "sans-serif" }}>
      <h1>Планирование отпусков</h1>
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
    </div>
  );
}

export function roleLabel(role: string): string {
  return roleLabelRu[role] ?? role;
}
