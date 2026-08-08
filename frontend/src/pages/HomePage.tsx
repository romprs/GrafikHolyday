import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../api/client";
import type { OrgUnitOut } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { roleLabel } from "./DevLoginPage";

export function HomePage() {
  const { currentUser, logout } = useAuth();
  const { data: orgUnits } = useQuery({
    queryKey: ["org-units"],
    queryFn: () => apiFetch<OrgUnitOut[]>("/org-units"),
  });

  if (!currentUser) return null;

  return (
    <div style={{ maxWidth: 640, margin: "2rem auto", fontFamily: "sans-serif" }}>
      <h1>Планирование отпусков</h1>
      <p>
        Вы вошли как <strong>{currentUser.full_name}</strong> (
        {roleLabel(currentUser.role)})
        {currentUser.has_benefits && " — есть льготы"}
      </p>
      <button onClick={logout}>Выйти</button>

      <h2>Оргструктура</h2>
      <ul>
        {orgUnits?.map((u) => (
          <li key={u.id}>
            {u.name} ({u.unit_kind})
          </li>
        ))}
      </ul>
    </div>
  );
}
