import { useQuery, useQueryClient } from "@tanstack/react-query";
import { grantRole, listUsersWithRoles, revokeRole } from "../api/admin";
import { useAuth } from "../auth/AuthContext";
import { roleLabel } from "./DevLoginPage";

export function RolesPage() {
  const queryClient = useQueryClient();
  const { currentUser } = useAuth();
  const { data: users } = useQuery({ queryKey: ["admin-users"], queryFn: listUsersWithRoles });

  async function handleGrant(userId: string) {
    await grantRole(userId, "hr_admin");
    queryClient.invalidateQueries({ queryKey: ["admin-users"] });
  }

  async function handleRevoke(userId: string) {
    await revokeRole(userId, "hr_admin");
    queryClient.invalidateQueries({ queryKey: ["admin-users"] });
  }

  return (
    <div>
      <h3>Управление ролями</h3>
      <p style={{ color: "#888", fontSize: "0.9em" }}>
        Сотрудник/руководитель определяются автоматически по оргструктуре. Вручную можно
        назначить только роль HR/администратор.
      </p>
      <table style={{ borderCollapse: "collapse", width: "100%" }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left" }}>Сотрудник</th>
            <th style={{ textAlign: "left" }}>Роль</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {users?.map((u) => (
            <tr key={u.id}>
              <td>
                {u.full_name} ({u.email})
              </td>
              <td>{roleLabel(u.role)}</td>
              <td>
                {u.role === "hr_admin" ? (
                  <button onClick={() => handleRevoke(u.id)} disabled={u.id === currentUser?.id}>
                    Забрать HR-admin
                  </button>
                ) : (
                  <button onClick={() => handleGrant(u.id)}>Выдать HR-admin</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
