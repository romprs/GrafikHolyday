import { useQuery, useQueryClient } from "@tanstack/react-query";
import { format, parseISO } from "date-fns";
import { ru } from "date-fns/locale/ru";
import { useMemo, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { apiFetch } from "../api/client";
import { getRestrictionSettings } from "../api/calendar";
import { isNonWorkingDay } from "../holidays";
import { approveLeaveRequest, rejectLeaveRequest } from "../api/leaveRequests";
import { getOrgLoadDetail } from "../api/orgLoad";
import type {
  EmployeeRole,
  LoadBand,
  OrgLoadEmployeeOut,
  OrgLoadLeaveEntryOut,
  OrgUnitOut,
} from "../api/types";

const statusLabel: Record<string, string> = {
  pending_approval: "на согласовании",
  approved: "согласовано",
};

const bandColor: Record<LoadBand, string> = {
  green: "#4caf50",
  yellow: "#fbc02d",
  red: "#e53935",
};

const bandLabel: Record<LoadBand, string> = {
  green: "до 30%",
  yellow: "30–50%",
  red: "более 50%",
};

const roleFilterLabel: Record<"all" | EmployeeRole, string> = {
  all: "Все",
  manager: "Руководители",
  employee: "Сотрудники",
  hr_admin: "HR/админ",
};

// ФИО хранится в формате "Фамилия Имя Отчество" — фамилия первым словом
// (см. app/integrations/org_directory.py, поле fio в реальных данных).
function surname(fullName: string): string {
  const parts = fullName.trim().split(/\s+/);
  return parts[0] ?? fullName;
}

function band(fraction: number, yellow: number, red: number): LoadBand {
  if (fraction > red) return "red";
  if (fraction > yellow) return "yellow";
  return "green";
}

const MONTH_NAMES = Array.from({ length: 12 }, (_, i) =>
  format(new Date(2000, i, 1), "LLLL", { locale: ru }),
);

function daysInMonth(year: number, monthIndex: number): number {
  return new Date(year, monthIndex + 1, 0).getDate();
}

function toIso(year: number, monthIndex: number, day: number): string {
  return format(new Date(year, monthIndex, day), "yyyy-MM-dd");
}

export function OrgLoadDashboardPage() {
  const { currentUser } = useAuth();
  const canApprove = currentUser?.role === "manager" || currentUser?.role === "hr_admin";
  const queryClient = useQueryClient();
  const { data: orgUnits } = useQuery({
    queryKey: ["org-units"],
    queryFn: () => apiFetch<OrgUnitOut[]>("/org-units"),
  });
  const { data: restrictionSettings } = useQuery({
    queryKey: ["restriction-settings"],
    queryFn: getRestrictionSettings,
  });
  const [selectedUnitId, setSelectedUnitId] = useState<string>("");
  const unitId = selectedUnitId || orgUnits?.[0]?.id || "";

  const { data: detail } = useQuery({
    queryKey: ["org-load-detail", unitId],
    queryFn: () => getOrgLoadDetail(unitId),
    enabled: !!unitId,
  });

  const [roleFilter, setRoleFilter] = useState<"all" | EmployeeRole>("all");
  const [search, setSearch] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [clickedDay, setClickedDay] = useState<string | null>(null);

  const thresholdsSetting = restrictionSettings?.find((s) => s.key === "department_load_thresholds");
  const yellowThreshold =
    typeof thresholdsSetting?.params.yellow === "number" ? thresholdsSetting.params.yellow : 0.3;
  const redThreshold =
    typeof thresholdsSetting?.params.red === "number" ? thresholdsSetting.params.red : 0.5;

  const planningYearSetting = restrictionSettings?.find((s) => s.key === "planning_year");
  const year =
    typeof planningYearSetting?.params.year === "number"
      ? planningYearSetting.params.year
      : new Date().getFullYear();

  const employees = detail?.employees ?? [];
  const leaves = detail?.leaves ?? [];

  const roleFilteredEmployees = useMemo(
    () => employees.filter((e) => roleFilter === "all" || e.role === roleFilter),
    [employees, roleFilter],
  );

  const searchFilteredEmployees = useMemo(() => {
    if (!search.trim()) return roleFilteredEmployees;
    const query = search.trim().toLowerCase();
    return roleFilteredEmployees.filter((e) => surname(e.full_name).toLowerCase().startsWith(query));
  }, [roleFilteredEmployees, search]);

  // Если сотрудники выбраны вручную — анализируем только их (для пересечений),
  // иначе — всех, кто прошёл фильтр по роли.
  const inScopeEmployees: OrgLoadEmployeeOut[] =
    selectedIds.size > 0
      ? roleFilteredEmployees.filter((e) => selectedIds.has(e.id))
      : roleFilteredEmployees;
  const inScopeIds = useMemo(() => new Set(inScopeEmployees.map((e) => e.id)), [inScopeEmployees]);

  const leavesInScope = useMemo(
    () => leaves.filter((l) => inScopeIds.has(l.user_id)),
    [leaves, inScopeIds],
  );

  const employeesById = useMemo(() => new Map(employees.map((e) => [e.id, e])), [employees]);

  function employeesOnLeave(dateIso: string): OrgLoadEmployeeOut[] {
    return leavesForDay(dateIso)
      .map((l) => employeesById.get(l.user_id))
      .filter((e): e is OrgLoadEmployeeOut => !!e);
  }

  function leavesForDay(dateIso: string): OrgLoadLeaveEntryOut[] {
    return leavesInScope.filter((l) => l.date_from <= dateIso && l.date_to >= dateIso);
  }

  function toggleSelected(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  // Один API-вызов — бэкенд согласует/отклоняет всю заявку (все периоды с
  // тем же submission_id) атомарно, group() тут больше не нужен.
  async function handleApproveSubmission(leave: OrgLoadLeaveEntryOut) {
    await approveLeaveRequest(leave.id);
    queryClient.invalidateQueries({ queryKey: ["org-load-detail", unitId] });
  }

  async function handleRejectSubmission(leave: OrgLoadLeaveEntryOut) {
    await rejectLeaveRequest(leave.id);
    queryClient.invalidateQueries({ queryKey: ["org-load-detail", unitId] });
  }

  const clickedDayLeaves = clickedDay ? leavesForDay(clickedDay) : [];

  return (
    <div>
      <h3>Отпуска подразделений ({year} год)</h3>
      <div>
        <label>
          Подразделение:{" "}
          <select value={unitId} onChange={(e) => setSelectedUnitId(e.target.value)}>
            {orgUnits?.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name} ({u.unit_kind})
              </option>
            ))}
          </select>
        </label>
      </div>

      <div style={{ display: "flex", gap: 24, alignItems: "flex-start", flexWrap: "wrap", marginTop: 12 }}>
        <div style={{ flex: "0 0 300px" }}>
          <label style={{ display: "block", marginBottom: 6 }}>
            Роль:{" "}
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value as "all" | EmployeeRole)}
            >
              {(["all", "manager", "employee"] as const).map((r) => (
                <option key={r} value={r}>
                  {roleFilterLabel[r]}
                </option>
              ))}
            </select>
          </label>
          <label style={{ display: "block", marginBottom: 6 }}>
            Поиск по фамилии:
            <input
              type="text"
              placeholder="напр. Иванов"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ display: "block", width: "100%", boxSizing: "border-box" }}
            />
          </label>

          <div
            style={{
              maxHeight: 480,
              overflowY: "auto",
              border: "1px solid #ddd",
              padding: 8,
            }}
          >
            {searchFilteredEmployees.length === 0 && (
              <p style={{ color: "#888", margin: 0 }}>Никого не найдено.</p>
            )}
            {searchFilteredEmployees.map((e) => (
              <label
                key={e.id}
                title={e.full_name}
                style={{ display: "flex", alignItems: "center", gap: 4 }}
              >
                <input
                  type="checkbox"
                  checked={selectedIds.has(e.id)}
                  onChange={() => toggleSelected(e.id)}
                />
                <span style={{ minWidth: 0, overflow: "hidden", whiteSpace: "nowrap", textOverflow: "ellipsis" }}>
                  {e.full_name}
                </span>
              </label>
            ))}
          </div>
          {selectedIds.size > 0 && (
            <p style={{ fontSize: "0.85em", color: "#888" }}>
              Выбрано вручную: {selectedIds.size} — анализируются пересечения только между ними.{" "}
              <button onClick={() => setSelectedIds(new Set())}>Сбросить выбор</button>
            </p>
          )}
          <p>
            В анализе: <strong>{inScopeEmployees.length}</strong> чел.
          </p>
        </div>

      <div style={{ flex: "1 1 700px", minWidth: 0 }}>
      <div style={{ overflowX: "auto" }}>
        <table style={{ borderCollapse: "collapse", fontSize: 15 }}>
          <thead>
            <tr>
              <th style={{ textAlign: "left", padding: "3px 12px 3px 0", whiteSpace: "nowrap" }}>
                Месяц
              </th>
              {Array.from({ length: 31 }, (_, i) => (
                <th key={i} style={{ width: 34, fontWeight: 400 }}>
                  {i + 1}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {MONTH_NAMES.map((monthName, monthIndex) => {
              const numDays = daysInMonth(year, monthIndex);
              return (
                <tr key={monthName}>
                  <td
                    style={{
                      textAlign: "left",
                      padding: "3px 12px 3px 0",
                      whiteSpace: "nowrap",
                      textTransform: "capitalize",
                      fontWeight: 600,
                    }}
                  >
                    {monthName}
                  </td>
                  {Array.from({ length: 31 }, (_, i) => {
                    const day = i + 1;
                    if (day > numDays) return <td key={day} />;
                    const dateIso = toIso(year, monthIndex, day);
                    const onLeave = employeesOnLeave(dateIso);
                    const fraction = inScopeEmployees.length
                      ? onLeave.length / inScopeEmployees.length
                      : 0;
                    const empty = onLeave.length === 0;
                    const nonWorking = isNonWorkingDay(new Date(year, monthIndex, day));
                    return (
                      <td key={day} style={{ padding: 2 }}>
                        <button
                          onClick={() => setClickedDay(dateIso)}
                          disabled={empty}
                          title={
                            empty
                              ? undefined
                              : `${dateIso}: ${onLeave.length} в отпуске — ${onLeave.map((e) => e.full_name).join(", ")}`
                          }
                          style={{
                            width: 32,
                            height: 32,
                            border: "none",
                            borderRadius: 4,
                            cursor: empty ? "default" : "pointer",
                            background: empty
                              ? nonWorking
                                ? "#ffe3e3"
                                : "#f0f0f0"
                              : bandColor[band(fraction, yellowThreshold, redThreshold)],
                            color: empty ? "#bbb" : "white",
                            fontSize: 13,
                            fontWeight: 600,
                          }}
                        >
                          {empty ? "" : onLeave.length}
                        </button>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div style={{ display: "flex", gap: 16, marginTop: 12, fontSize: "0.85em" }}>
        {(["green", "yellow", "red"] as LoadBand[]).map((b) => (
          <span key={b} style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span
              style={{
                display: "inline-block",
                width: 12,
                height: 12,
                background: bandColor[b],
                borderRadius: 2,
              }}
            />
            {bandLabel[b]}
          </span>
        ))}
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span
            style={{
              display: "inline-block",
              width: 12,
              height: 12,
              background: "#f0f0f0",
              borderRadius: 2,
            }}
          />
          нет отпусков (клик недоступен)
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span
            style={{
              display: "inline-block",
              width: 12,
              height: 12,
              background: "#ffe3e3",
              borderRadius: 2,
            }}
          />
          выходной/праздник
        </span>
      </div>
      </div>

      {clickedDay && (
        <div
          style={{
            position: "fixed",
            top: 96,
            right: 24,
            width: 280,
            border: "1px solid #ccc",
            borderRadius: 6,
            padding: 12,
            maxHeight: "70vh",
            overflowY: "auto",
            background: "#fff",
            boxShadow: "0 4px 16px rgba(0,0,0,0.2)",
            zIndex: 100,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
            <strong>{format(parseISO(clickedDay), "dd.MM.yyyy")}</strong>
            <button
              type="button"
              onClick={() => setClickedDay(null)}
              title="Закрыть"
              style={{
                border: "none",
                background: "none",
                cursor: "pointer",
                fontSize: 20,
                lineHeight: 1,
                padding: 0,
                color: "#888",
              }}
            >
              ×
            </button>
          </div>
          <ul style={{ margin: "8px 0 0 0", paddingLeft: 20 }}>
            {clickedDayLeaves.map((l) => {
              const employee = employeesById.get(l.user_id);
              const fullName = employee?.full_name ?? "—";
              return (
                <li key={l.id} style={{ marginBottom: 6 }}>
                  <div
                    title={fullName}
                    style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}
                  >
                    {fullName}
                  </div>
                  <span style={{ color: l.status === "approved" ? "#2e7d32" : "#a06a00" }}>
                    {statusLabel[l.status] ?? l.status}
                  </span>
                  {canApprove && l.status === "pending_approval" && (
                    <div style={{ marginTop: 2 }}>
                      <button onClick={() => handleApproveSubmission(l)}>Согласовать</button>{" "}
                      <button onClick={() => handleRejectSubmission(l)}>Отклонить</button>
                    </div>
                  )}
                </li>
              );
            })}
            {clickedDayLeaves.length === 0 && <li>Никто не в отпуске</li>}
          </ul>
        </div>
      )}
      </div>
    </div>
  );
}
