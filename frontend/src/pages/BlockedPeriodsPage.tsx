import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { apiFetch, ApiError } from "../api/client";
import {
  createBlockedPeriod,
  deleteBlockedPeriod,
  getRestrictionSettings,
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
  const { data: restrictionSettings } = useQuery({
    queryKey: ["restriction-settings"],
    queryFn: getRestrictionSettings,
  });
  const employeeName = (id: string) =>
    employees?.find((e) => e.id === id)?.full_name ?? id;

  const planningYearSetting = restrictionSettings?.find((s) => s.key === "planning_year");
  const planningYear =
    typeof planningYearSetting?.params.year === "number"
      ? planningYearSetting.params.year
      : new Date().getFullYear();

  // Список годов для фильтра — плановый год плюс все года, которые реально
  // встречаются в данных (периоды блокировок могут выходить за его пределы).
  const availableYears = useMemo(() => {
    const years = new Set<number>([planningYear]);
    for (const b of blockedPeriods ?? []) {
      years.add(new Date(b.date_from).getFullYear());
      years.add(new Date(b.date_to).getFullYear());
    }
    return Array.from(years).sort((a, b) => b - a);
  }, [blockedPeriods, planningYear]);

  const [yearFilter, setYearFilter] = useState<number | "">(planningYear);
  const [scopeFilter, setScopeFilter] = useState<BlockedPeriodScope | "">("");
  const [search, setSearch] = useState("");

  const filteredBlockedPeriods = useMemo(() => {
    let list = blockedPeriods ?? [];
    if (yearFilter !== "") {
      const yearStart = `${yearFilter}-01-01`;
      const yearEnd = `${yearFilter}-12-31`;
      list = list.filter((b) => b.date_from <= yearEnd && b.date_to >= yearStart);
    }
    if (scopeFilter !== "") {
      list = list.filter((b) => b.scope === scopeFilter);
    }
    const query = search.trim().toLowerCase();
    if (query) {
      list = list.filter((b) => {
        const target = b.scope === "user" ? employeeName(b.user_id ?? "") : "";
        return target.toLowerCase().includes(query) || b.reason.toLowerCase().includes(query);
      });
    }
    return list;
  }, [blockedPeriods, yearFilter, scopeFilter, search, employees]);

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

      <form onSubmit={handleCreate} className="panel" style={{ maxWidth: 420 }}>
        <div className="fieldrow">
          <div className="field" style={{ flex: 1 }}>
            <label>Дата начала</label>
            <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} required />
          </div>
          <div className="field" style={{ flex: 1 }}>
            <label>Дата окончания</label>
            <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} required />
          </div>
        </div>
        <div className="field" style={{ marginBottom: 14 }}>
          <label>Причина</label>
          <input type="text" value={reason} onChange={(e) => setReason(e.target.value)} required />
        </div>
        <div className="field" style={{ marginBottom: 14 }}>
          <label>Область действия</label>
          <select value={scope} onChange={(e) => setScope(e.target.value as BlockedPeriodScope)}>
            <option value="org_unit">Подразделение</option>
            <option value="user">Сотрудник</option>
            <option value="global">Вся компания (HR/админ)</option>
          </select>
        </div>
        {scope === "org_unit" && (
          <div className="field" style={{ marginBottom: 14 }}>
            <label>Подразделение</label>
            <select value={orgUnitId} onChange={(e) => setOrgUnitId(e.target.value)} required>
              <option value="" disabled>
                — выберите —
              </option>
              {orgUnits?.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name}
                </option>
              ))}
            </select>
          </div>
        )}
        {scope === "user" && (
          <div className="field" style={{ marginBottom: 14 }}>
            <label>Сотрудник</label>
            <select value={userId} onChange={(e) => setUserId(e.target.value)} required>
              <option value="" disabled>
                — выберите —
              </option>
              {employees?.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.full_name} ({e.email})
                </option>
              ))}
            </select>
          </div>
        )}
        <button type="submit" className="btn-primary">
          Добавить блокировку
        </button>
        {error && <p className="error-text">{error}</p>}
      </form>

      <div className="toolbar" style={{ marginTop: 20 }}>
        <div className="field" style={{ width: 140 }}>
          <label>Плановый год</label>
          <select value={yearFilter} onChange={(e) => setYearFilter(e.target.value === "" ? "" : Number(e.target.value))}>
            <option value="">Все года</option>
            {availableYears.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </div>
        <div className="field" style={{ width: 180 }}>
          <label>Область</label>
          <select value={scopeFilter} onChange={(e) => setScopeFilter(e.target.value as BlockedPeriodScope | "")}>
            <option value="">Все</option>
            <option value="global">Вся компания</option>
            <option value="org_unit">Подразделение</option>
            <option value="user">Сотрудник</option>
          </select>
        </div>
        <div className="field" style={{ flex: 1, minWidth: 200 }}>
          <label>Поиск (сотрудник/причина)</label>
          <input type="text" placeholder="напр. Иванов или Курс" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
      </div>

      <div className="panel">
        <table className="t">
          <thead>
            <tr>
              <th>Период</th>
              <th>Причина</th>
              <th>Область</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {filteredBlockedPeriods.map((b) => (
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
                  <button className="btn-ghost" onClick={() => handleDelete(b.id)}>
                    Удалить
                  </button>
                </td>
              </tr>
            ))}
            {filteredBlockedPeriods.length === 0 && (
              <tr>
                <td colSpan={4} className="empty">
                  Ничего не найдено.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
