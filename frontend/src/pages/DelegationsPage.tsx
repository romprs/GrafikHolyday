import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  createDelegation,
  listDelegationDirectory,
  listDelegations,
  revokeDelegation,
} from "../api/delegations";
import { apiFetch, ApiError } from "../api/client";
import type { DelegationTargetOut, OrgUnitEmployeeOut } from "../api/types";

export function DelegationsPage() {
  const queryClient = useQueryClient();
  const { data: delegations } = useQuery({ queryKey: ["delegations"], queryFn: listDelegations });
  const { data: directory } = useQuery({
    queryKey: ["delegation-directory"],
    queryFn: listDelegationDirectory,
  });
  // Цель делегирования — только сотрудники из своей зоны ответственности
  // (для HR это все, для руководителя — своя ветка, см. /org-units/employees).
  const { data: employees } = useQuery({
    queryKey: ["org-unit-employees"],
    queryFn: () => apiFetch<OrgUnitEmployeeOut[]>("/org-units/employees"),
  });

  const [delegateId, setDelegateId] = useState("");
  const [targetId, setTargetId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const nameById = new Map<string, string>();
  for (const d of directory ?? []) nameById.set(d.id, `${d.full_name} (${d.email})`);
  const target = (id: string) => nameById.get(id) ?? id;

  async function handleGrant(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createDelegation({ delegate_user_id: delegateId, target_user_id: targetId });
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
          За кого (сотрудник)
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
              <td>{target(d.delegate_user_id)}</td>
              <td>{target(d.target_user_id)}</td>
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
