import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  createDelegation,
  listDelegationDirectory,
  listDelegations,
  revokeDelegation,
} from "../api/delegations";
import { apiFetch, ApiError } from "../api/client";
import type { DelegationTargetOut, LeaveDelegationScope, OrgUnitEmployeeOut, OrgUnitOut } from "../api/types";

export function DelegationsPage() {
  const queryClient = useQueryClient();
  const { data: delegations } = useQuery({ queryKey: ["delegations"], queryFn: listDelegations });
  const { data: directory } = useQuery({
    queryKey: ["delegation-directory"],
    queryFn: listDelegationDirectory,
  });
  // Цель делегирования — только сотрудники/подразделения из своей зоны
  // ответственности (для HR это всё, для руководителя — своя ветка).
  const { data: employees } = useQuery({
    queryKey: ["org-unit-employees"],
    queryFn: () => apiFetch<OrgUnitEmployeeOut[]>("/org-units/employees"),
  });
  const { data: orgUnits } = useQuery({
    queryKey: ["org-units"],
    queryFn: () => apiFetch<OrgUnitOut[]>("/org-units"),
  });

  const [delegateId, setDelegateId] = useState("");
  const [scope, setScope] = useState<LeaveDelegationScope>("user");
  const [targetId, setTargetId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const nameById = new Map<string, string>();
  for (const d of directory ?? []) nameById.set(d.id, `${d.full_name} (${d.email})`);
  const userLabel = (id: string) => nameById.get(id) ?? id;
  const unitNameById = new Map((orgUnits ?? []).map((u) => [u.id, u.name]));
  const unitLabel = (id: string) => unitNameById.get(id) ?? id;

  async function handleGrant(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createDelegation({
        delegate_user_id: delegateId,
        target_user_id: scope === "user" ? targetId : undefined,
        target_org_unit_id: scope === "org_unit" ? targetId : undefined,
      });
      setDelegateId("");
      setTargetId("");
      queryClient.invalidateQueries({ queryKey: ["delegations"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось выдать делегирование");
    }
  }

  async function handleRevoke(id: string) {
    await revokeDelegation(id);
    queryClient.invalidateQueries({ queryKey: ["delegations"] });
  }

  const active = (delegations ?? []).filter((d) => d.is_active);

  return (
    <div>
      <h3>Делегирование заявок</h3>
      <p style={{ color: "#888", fontSize: "0.9em" }}>
        Право подавать и вести заявки на отпуск от имени сотрудника, который сам системой не
        пользуется — делегатом может быть любой сотрудник, в том числе из другого подразделения.
        Можно делегировать одного сотрудника или сразу всё подразделение (и нижестоящие) —
        удобно, когда за отдел отвечает один человек.
      </p>

      <form
        onSubmit={handleGrant}
        style={{ display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap", marginBottom: 16 }}
      >
        <label>
          Делегат (кто будет подавать)
          <select
            value={delegateId}
            onChange={(e) => setDelegateId(e.target.value)}
            required
            style={{ display: "block", minWidth: 240 }}
          >
            <option value="" disabled>
              — выберите —
            </option>
            {directory?.map((d: DelegationTargetOut) => (
              <option key={d.id} value={d.id}>
                {d.full_name} ({d.email})
              </option>
            ))}
          </select>
        </label>
        <label>
          За кого
          <select
            value={scope}
            onChange={(e) => {
              setScope(e.target.value as LeaveDelegationScope);
              setTargetId("");
            }}
            style={{ display: "block" }}
          >
            <option value="user">Одного сотрудника</option>
            <option value="org_unit">Всё подразделение</option>
          </select>
        </label>
        {scope === "user" ? (
          <label>
            Сотрудник
            <select
              value={targetId}
              onChange={(e) => setTargetId(e.target.value)}
              required
              style={{ display: "block", minWidth: 240 }}
            >
              <option value="" disabled>
                — выберите —
              </option>
              {employees?.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.full_name} ({e.email})
                </option>
              ))}
            </select>
          </label>
        ) : (
          <label>
            Подразделение
            <select
              value={targetId}
              onChange={(e) => setTargetId(e.target.value)}
              required
              style={{ display: "block", minWidth: 240 }}
            >
              <option value="" disabled>
                — выберите —
              </option>
              {orgUnits?.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <button type="submit">Выдать</button>
        {error && <span style={{ color: "crimson" }}>{error}</span>}
      </form>

      <table style={{ borderCollapse: "collapse", width: "100%" }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left" }}>Делегат</th>
            <th style={{ textAlign: "left" }}>За кого</th>
            <th style={{ textAlign: "left" }}>Выдано</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {active.length === 0 && (
            <tr>
              <td colSpan={4} style={{ color: "#888" }}>
                Делегирований нет.
              </td>
            </tr>
          )}
          {active.map((d) => (
            <tr key={d.id}>
              <td>{userLabel(d.delegate_user_id)}</td>
              <td>
                {d.scope === "user"
                  ? userLabel(d.target_user_id ?? "")
                  : `Подразделение: ${unitLabel(d.target_org_unit_id ?? "")} (и нижестоящие)`}
              </td>
              <td>{new Date(d.created_at).toLocaleDateString("ru-RU")}</td>
              <td>
                <button onClick={() => handleRevoke(d.id)}>Отозвать</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
