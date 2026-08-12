import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  createDelegation,
  listDelegationDirectory,
  listDelegations,
  revokeDelegation,
} from "../api/delegations";
import { apiFetch, ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { DelegationTargetOut, LeaveDelegationScope, OrgUnitEmployeeOut, OrgUnitOut } from "../api/types";

// ФИО хранится в формате "Фамилия Имя Отчество" — фамилия первым словом
// (см. app/integrations/org_directory.py, поле fio в реальных данных).
function surname(fullName: string): string {
  const parts = fullName.trim().split(/\s+/);
  return parts[0] ?? fullName;
}

export function DelegationsPage() {
  const { currentUser } = useAuth();
  const isHrAdmin = currentUser?.role === "hr_admin";
  const queryClient = useQueryClient();
  const { data: delegations } = useQuery({ queryKey: ["delegations"], queryFn: listDelegations });
  // Полный список сотрудников (любое подразделение) — источник для выбора
  // делегата у HR (не привязан к чьей-то конкретной ветке) и для отображения
  // имён в уже выданных делегированиях (там может быть кто угодно, даже
  // если сам список выбора у руководителя теперь уже — см. employees ниже).
  const { data: directory } = useQuery({
    queryKey: ["delegation-directory"],
    queryFn: listDelegationDirectory,
  });
  // Цель делегирования — только сотрудники/подразделения из своей зоны
  // ответственности (для HR это всё, для руководителя — своя ветка). У
  // руководителя делегатом тоже может быть только кто-то из своей ветки —
  // просить согласовывать заявки постороннего человека из другого отдела
  // смысла нет, поэтому используем тот же скоуп и для выбора делегата.
  const { data: employees } = useQuery({
    queryKey: ["org-unit-employees"],
    queryFn: () => apiFetch<OrgUnitEmployeeOut[]>("/org-units/employees"),
  });
  const { data: orgUnits } = useQuery({
    queryKey: ["org-units"],
    queryFn: () => apiFetch<OrgUnitOut[]>("/org-units"),
  });

  const [delegateId, setDelegateId] = useState("");
  const [delegateSearch, setDelegateSearch] = useState("");
  const [scope, setScope] = useState<LeaveDelegationScope>("user");
  const [targetId, setTargetId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const delegateCandidates: DelegationTargetOut[] = isHrAdmin
    ? directory ?? []
    : (employees ?? []).map((e) => ({ id: e.id, full_name: e.full_name, email: e.email }));
  const filteredDelegateCandidates = useMemo(() => {
    const query = delegateSearch.trim().toLowerCase();
    if (!query) return delegateCandidates;
    return delegateCandidates.filter((d) => surname(d.full_name).toLowerCase().startsWith(query));
  }, [delegateCandidates, delegateSearch]);

  const nameById = new Map<string, string>();
  for (const d of directory ?? []) nameById.set(d.id, `${d.full_name} (${d.email})`);
  for (const e of employees ?? []) nameById.set(e.id, `${e.full_name} (${e.email})`);
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
        пользуется.{" "}
        {isHrAdmin
          ? "Делегатом может быть любой сотрудник, в том числе из другого подразделения."
          : "Делегатом может быть сотрудник из вашей ветки подчинения."}{" "}
        Можно делегировать одного сотрудника или сразу всё подразделение (и нижестоящие) —
        удобно, когда за отдел отвечает один человек.
      </p>

      <form
        onSubmit={handleGrant}
        style={{ display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap", marginBottom: 16 }}
      >
        <label>
          Поиск делегата по фамилии
          <input
            type="text"
            placeholder="напр. Иванов"
            value={delegateSearch}
            onChange={(e) => setDelegateSearch(e.target.value)}
            style={{ display: "block", width: 200 }}
          />
        </label>
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
            {filteredDelegateCandidates.map((d: DelegationTargetOut) => (
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
