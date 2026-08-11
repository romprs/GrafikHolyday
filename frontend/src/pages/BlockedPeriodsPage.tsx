import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiFetch, ApiError } from "../api/client";
import {
  createBlockedPeriod,
  deleteBlockedPeriod,
  listBlockedPeriods,
} from "../api/calendar";
import type { BlockedPeriodScope, OrgUnitEmployeeOut, OrgUnitOut } from "../api/types";

export function BlockedPeriodsPage() {
  const queryClient = useQueryClient();
  const { data: blockedPeriods } = useQuery({
    queryKey: ["blocked-periods"],
    queryFn: listBlockedPeriods,
  });
  const { data: orgUnits } = useQuery({
    queryKey: ["org-units"],
    queryFn: () => apiFetch<OrgUnitOut[]>("/org-units"),
  });
  const { data: employees } = useQuery({
    queryKey: ["org-unit-employees"],
    queryFn: () => apiFetch<OrgUnitEmployeeOut[]>("/org-units/employees"),
  });
  const employeeName = (id: string) =>
    employees?.find((e) => e.id === id)?.full_name ?? id;

  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [reason, setReason] = useState("");
  const [scope, setScope] = useState<BlockedPeriodScope>("org_unit");
  const [orgUnitId, setOrgUnitId] = useState("");
  const [userId, setUserId] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createBlockedPeriod({
        date_from: dateFrom,
        date_to: dateTo,
        reason,
        scope,
        org_unit_id: scope === "org_unit" ? orgUnitId : null,
        user_id: scope === "user" ? userId : null,
      });
      setDateFrom("");
      setDateTo("");
      setReason("");
      queryClient.invalidateQueries({ queryKey: ["blocked-periods"] });
      queryClient.invalidateQueries({ queryKey: ["blocked-ranges"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось создать блокировку");
    }
  }

  async function handleDelete(id: string) {
    await deleteBlockedPeriod(id);
    queryClient.invalidateQueries({ queryKey: ["blocked-periods"] });
    queryClient.invalidateQueries({ queryKey: ["blocked-ranges"] });
  }

  return (
    <div>
      <h3>Недоступные периоды</h3>

      <form onSubmit={handleCreate} style={{ display: "flex", flexDirection: "column", gap: 8, maxWidth: 400 }}>
        <label>
          Дата начала
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            required
            style={{ display: "block" }}
          />
        </label>
        <label>
          Дата окончания
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            required
            style={{ display: "block" }}
          />
        </label>
        <label>
          Причина
          <input
            type="text"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            required
            style={{ display: "block", width: "100%" }}
          />
        </label>
        <label>
          Область действия
          <select
            value={scope}
            onChange={(e) => setScope(e.target.value as BlockedPeriodScope)}
            style={{ display: "block" }}
          >
            <option value="org_unit">Подразделение</option>
            <option value="user">Сотрудник</option>
            <option value="global">Вся компания (HR/админ)</option>
          </select>
        </label>
        {scope === "org_unit" && (
          <label>
            Подразделение
            <select
              value={orgUnitId}
              onChange={(e) => setOrgUnitId(e.target.value)}
              required
              style={{ display: "block" }}
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
        {scope === "user" && (
          <label>
            Сотрудник
            <select
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              required
              style={{ display: "block" }}
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
        )}
        <button type="submit">Добавить блокировку</button>
        {error && <p style={{ color: "crimson" }}>{error}</p>}
      </form>

      <table style={{ borderCollapse: "collapse", width: "100%", marginTop: 16 }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left" }}>Период</th>
            <th style={{ textAlign: "left" }}>Причина</th>
            <th style={{ textAlign: "left" }}>Область</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {blockedPeriods?.map((b) => (
            <tr key={b.id}>
              <td>
                {b.date_from} — {b.date_to}
              </td>
              <td>{b.reason}</td>
              <td>
                {b.scope === "global" && "Вся компания"}
                {b.scope === "org_unit" && "Подразделение"}
                {b.scope === "user" && `Сотрудник: ${employeeName(b.user_id ?? "")}`}
              </td>
              <td>
                <button onClick={() => handleDelete(b.id)}>Удалить</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
