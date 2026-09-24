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
  draft: "черновик",
  pending_approval: "на согласовании",
  approved: "согласовано",
  rejected: "отклонено",
  cancelled: "отменено",
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
  const canApprove =
    currentUser?.role === "manager" || currentUser?.role === "hr_admin" || !!currentUser?.is_approver;
  const queryClient = useQueryClient();
  const { data: orgUnits } = useQuery({
    queryKey: ["org-units"],
    queryFn: () => apiFetch<OrgUnitOut[]>("/org-units"),
  });
  const { data: restrictionSettings } = useQuery({
    queryKey: ["restriction-settings"],
    queryFn: getRestrictionSettings,
  });
  // Руководитель не может согласовать сам себе (см. approval_service._is_manager_of) —
  // единственное исключение бэкенда: сам возглавляет подразделение без родителя
  // (замгендиректора и приравненные). Кнопку прячем заранее, а не показываем
  // нерабочей — старая ошибка того же рода уже чинилась в очереди согласования
  // (Phase 6.30), здесь она осталась на этом отдельном графике.
  const selfApprovalExempt = useMemo(
    () =>
      !!currentUser &&
      (orgUnits ?? []).some((u) => u.head_user_id === currentUser.id && u.parent_id === null),
    [orgUnits, currentUser],
  );
  // Деактивированные подразделения не выбираются на этом графике — как и
  // на дашборде загруженности, тут нет смысла смотреть отпуска расформированного отдела.
  const activeOrgUnits = useMemo(() => (orgUnits ?? []).filter((u) => u.is_active), [orgUnits]);

  const [selectedUnitId, setSelectedUnitId] = useState<string>("");
  const unitId = selectedUnitId || activeOrgUnits[0]?.id || "";

  const { data: detail } = useQuery({
    queryKey: ["org-load-detail", unitId],
    queryFn: () => getOrgLoadDetail(unitId),
    enabled: !!unitId,
  });

  const [roleFilter, setRoleFilter] = useState<"all" | EmployeeRole>("all");
  const [search, setSearch] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [clickedDay, setClickedDay] = useState<string | null>(null);
  // Сотрудник, чьи периоды сейчас подсвечиваются на всём графике — отдельно
  // от selectedIds (тот набор — для анализа пересечений загрузки, этот —
  // просто "показать, когда этот человек в отпуске", по всему году сразу,
  // без фильтров по роли/поиску/выбору.
  const [focusedEmployeeId, setFocusedEmployeeId] = useState<string | null>(null);

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

  const focusedEmployee = focusedEmployeeId ? employeesById.get(focusedEmployeeId) : undefined;
  // Из ВСЕХ отпусков подразделения (не только leavesInScope) — подсветка не
  // должна зависеть от текущего фильтра по роли/поиску/ручному выбору.
  const focusedLeaves = useMemo(
    () => (focusedEmployeeId ? leaves.filter((l) => l.user_id === focusedEmployeeId) : []),
    [leaves, focusedEmployeeId],
  );

  function isFocusedDay(dateIso: string): boolean {
    return focusedLeaves.some((l) => l.date_from <= dateIso && l.date_to >= dateIso);
  }

  function toggleFocused(id: string) {
    setFocusedEmployeeId((prev) => (prev === id ? null : id));
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
  // Раньше ошибка бэкенда (например, 403 «вы не руководитель отдела этого
  // сотрудника» для HR-админа, не возглавляющего этот отдел) молча
  // терялась — кнопка выглядела просто нерабочей.
  async function reviewSubmission(action: typeof approveLeaveRequest, leave: OrgLoadLeaveEntryOut) {
    try {
      await action(leave.id);
      queryClient.invalidateQueries({ queryKey: ["org-load-detail", unitId] });
    } catch (err) {
      window.alert(err instanceof Error ? err.message : "Не удалось выполнить действие");
    }
  }

  const handleApproveSubmission = (leave: OrgLoadLeaveEntryOut) => reviewSubmission(approveLeaveRequest, leave);
  const handleRejectSubmission = (leave: OrgLoadLeaveEntryOut) => reviewSubmission(rejectLeaveRequest, leave);

  const clickedDayLeaves = clickedDay ? leavesForDay(clickedDay) : [];
  // Показываем сразу, без клика по дню — весь список несогласованных заявок
  // в текущей области анализа. Группируем по submission_id: один человек —
  // одна заявка (пусть даже из нескольких периодов), согласуется/отклоняется
  // целиком одним действием — тот же принцип, что и в ApprovalQueuePage.
  const pendingSubmissions = useMemo(() => {
    const groups = new Map<string, OrgLoadLeaveEntryOut[]>();
    for (const l of leavesInScope) {
      if (l.status !== "pending_approval") continue;
      const key = l.submission_id ?? l.id;
      const list = groups.get(key) ?? [];
      list.push(l);
      groups.set(key, list);
    }
    return Array.from(groups.values())
      .map((requests) => requests.sort((a, b) => a.date_from.localeCompare(b.date_from)))
      .sort((a, b) => a[0].date_from.localeCompare(b[0].date_from));
  }, [leavesInScope]);

  return (
    <div>
      <h3>Отпуска подразделений ({year} год)</h3>
      <div className="panel field" style={{ maxWidth: 360, marginBottom: 12 }}>
        <label>Подразделение</label>
        <select value={unitId} onChange={(e) => setSelectedUnitId(e.target.value)}>
          {activeOrgUnits.map((u) => (
            <option key={u.id} value={u.id}>
              {u.unit_kind ? `${u.name} (${u.unit_kind})` : u.name}
            </option>
          ))}
        </select>
      </div>

      {/* Без переноса: при сужении окна календарь остаётся справа от
          фильтра, а ряд прокручивается по горизонтали (раньше wrap
          сбрасывал календарь под фильтр). */}
      <div style={{ display: "flex", gap: 24, alignItems: "flex-start", flexWrap: "nowrap", overflowX: "auto", marginTop: 12 }}>
        <div className="panel" style={{ flex: "0 0 300px", minWidth: 0 }}>
          <div className="field" style={{ marginBottom: 10 }}>
            <label>Роль</label>
            <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value as "all" | EmployeeRole)}>
              {(["all", "manager", "employee"] as const).map((r) => (
                <option key={r} value={r}>
                  {roleFilterLabel[r]}
                </option>
              ))}
            </select>
          </div>
          <div className="field" style={{ marginBottom: 10 }}>
            <label>Поиск по фамилии</label>
            <input
              type="text"
              placeholder="напр. Иванов"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ width: "100%" }}
            />
          </div>

          <div
            style={{
              maxHeight: 480,
              overflowY: "auto",
              overflowX: "hidden",
              border: "1px solid var(--line)",
              borderRadius: 10,
              padding: 8,
            }}
          >
            {searchFilteredEmployees.length === 0 && <p className="empty" style={{ margin: 0 }}>Никого не найдено.</p>}
            {searchFilteredEmployees.map((e) => (
              <div key={e.id} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <input type="checkbox" checked={selectedIds.has(e.id)} onChange={() => toggleSelected(e.id)} />
                <button
                  type="button"
                  onClick={() => toggleFocused(e.id)}
                  title={`${e.full_name} — показать все периоды на графике`}
                  style={{
                    minWidth: 0,
                    overflow: "hidden",
                    whiteSpace: "nowrap",
                    textOverflow: "ellipsis",
                    background: "none",
                    border: "none",
                    padding: "4px 0",
                    textAlign: "left",
                    cursor: "pointer",
                    color: focusedEmployeeId === e.id ? "var(--accent-ink)" : "inherit",
                    fontWeight: focusedEmployeeId === e.id ? 700 : 400,
                  }}
                >
                  {e.full_name}
                </button>
              </div>
            ))}
          </div>
          {selectedIds.size > 0 && (
            <p className="hint">
              Выбрано вручную: {selectedIds.size} — анализируются пересечения только между ними.{" "}
              <button className="btn-ghost" style={{ padding: "2px 6px" }} onClick={() => setSelectedIds(new Set())}>
                Сбросить выбор
              </button>
            </p>
          )}
          {focusedEmployee && (
            <p style={{ fontSize: "0.85em", color: "var(--accent-ink)" }}>
              Показаны все периоды: <strong>{focusedEmployee.full_name}</strong> (обведены на графике).{" "}
              <button className="btn-ghost" style={{ padding: "2px 6px" }} onClick={() => setFocusedEmployeeId(null)}>
                Убрать подсветку
              </button>
            </p>
          )}
          <p className="hint" style={{ marginBottom: 0 }}>
            В анализе: <strong style={{ color: "var(--ink)" }}>{inScopeEmployees.length}</strong> чел.
          </p>
        </div>

      {/* flex: "0 0 auto" + фиксированная ширина — раньше было "1 1 0px"
          (тянуться на всё доступное место), из-за чего сама карточка вокруг
          календаря сжималась и растягивалась вместе с окном браузера, хотя
          колонки внутри таблицы уже были зафиксированы. Теперь ширина
          карточки не зависит от окна вообще: у неё столько же места, сколько
          нужно таблице (плюс паддинги .panel), не больше и не меньше. */}
      <div className="panel" style={{ flex: "0 0 auto", width: 110 + 31 * 34 + 38 }}>
      <div style={{ overflowX: "auto" }}>
        {/* Явная ширина = сумма колонок (110 + 31×34) — без неё браузер при
            table-layout:fixed всё равно тянет таблицу по ширине родителя и
            пропорционально растягивает/сжимает колонки при изменении
            размера окна вместо того, чтобы просто скроллить контейнер. */}
        <table style={{ borderCollapse: "collapse", fontSize: 15, tableLayout: "fixed", width: 110 + 31 * 34 }}>
          <colgroup>
            <col style={{ width: 110 }} />
            {Array.from({ length: 31 }, (_, i) => (
              <col key={i} style={{ width: 34 }} />
            ))}
          </colgroup>
          <thead>
            <tr>
              <th style={{ textAlign: "left", padding: "3px 12px 3px 0", whiteSpace: "nowrap" }}>
                Месяц
              </th>
              {Array.from({ length: 31 }, (_, i) => (
                <th key={i} style={{ fontWeight: 400 }}>
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
                    const dayLeaves = leavesForDay(dateIso);
                    const hasPending = dayLeaves.some((l) => l.status === "pending_approval");
                    const fraction = inScopeEmployees.length
                      ? onLeave.length / inScopeEmployees.length
                      : 0;
                    const empty = onLeave.length === 0;
                    const nonWorking = isNonWorkingDay(new Date(year, monthIndex, day));
                    const focused = isFocusedDay(dateIso);
                    return (
                      <td key={day} style={{ padding: 2 }}>
                        <button
                          onClick={() => setClickedDay(dateIso)}
                          disabled={empty}
                          title={
                            empty
                              ? undefined
                              : `${dateIso}: ${onLeave.length} в отпуске — ${onLeave.map((e) => e.full_name).join(", ")}` +
                                (hasPending ? " (есть несогласованные)" : " (все согласованы)")
                          }
                          style={{
                            width: 32,
                            height: 32,
                            border: hasPending ? "2px dashed var(--wait-fg)" : "2px solid transparent",
                            borderRadius: 6,
                            boxSizing: "border-box",
                            boxShadow: focused ? "inset 0 0 0 2px var(--accent-ink)" : undefined,
                            cursor: empty ? "default" : "pointer",
                            background: empty
                              ? nonWorking
                                ? "var(--holiday-bg)"
                                : "var(--empty-bg)"
                              : bandColor[band(fraction, yellowThreshold, redThreshold)],
                            color: empty ? "var(--empty-fg)" : "white",
                            fontSize: 13,
                            fontWeight: 700,
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
              background: "var(--empty-bg)",
              borderRadius: 3,
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
              background: "var(--holiday-bg)",
              borderRadius: 3,
            }}
          />
          выходной/праздник
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span
            style={{
              display: "inline-block",
              width: 12,
              height: 12,
              border: "2px dashed var(--wait-fg)",
              boxSizing: "border-box",
              borderRadius: 3,
            }}
          />
          есть несогласованные заявки
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span
            style={{
              display: "inline-block",
              width: 12,
              height: 12,
              boxShadow: "inset 0 0 0 2px var(--accent-ink)",
              boxSizing: "border-box",
              borderRadius: 3,
            }}
          />
          дни выбранного сотрудника
        </span>
      </div>
      </div>

      <div className="panel" style={{ flex: "0 0 260px", maxHeight: "70vh", overflowY: "auto", position: "sticky", top: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
          <strong>
            {clickedDay
              ? format(parseISO(clickedDay), "dd.MM.yyyy")
              : `На согласовании (${pendingSubmissions.length})`}
          </strong>
          {clickedDay && (
            <button
              type="button"
              onClick={() => setClickedDay(null)}
              title="Вернуться к списку несогласованных"
              className="btn-ghost"
              style={{ fontSize: 18, lineHeight: 1, padding: "2px 6px" }}
            >
              ×
            </button>
          )}
        </div>
        {clickedDay ? (
          <ul style={{ margin: "8px 0 0 0", paddingLeft: 20 }}>
            {clickedDayLeaves.map((l) => {
              const employee = employeesById.get(l.user_id);
              const fullName = employee?.full_name ?? "—";
              const isSelf = l.user_id === currentUser?.id;
              return (
                <li key={l.id} style={{ marginBottom: 6 }}>
                  <button
                    type="button"
                    onClick={() => toggleFocused(l.user_id)}
                    title={`${fullName} — показать все периоды на графике`}
                    style={{
                      display: "block",
                      width: "100%",
                      textAlign: "left",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      background: "none",
                      border: "none",
                      padding: 0,
                      cursor: "pointer",
                      color: focusedEmployeeId === l.user_id ? "var(--accent-ink)" : "inherit",
                      fontWeight: focusedEmployeeId === l.user_id ? 700 : 400,
                    }}
                  >
                    {fullName}
                  </button>
                  <span className={`badge ${l.status === "approved" ? "ok" : "wait"}`}>
                    {statusLabel[l.status] ?? l.status}
                  </span>
                  {canApprove && l.status === "pending_approval" && (!isSelf || selfApprovalExempt) && (
                    <div style={{ marginTop: 4 }}>
                      <button className="btn-ghost" style={{ padding: "4px 8px" }} onClick={() => handleApproveSubmission(l)}>
                        Согласовать
                      </button>{" "}
                      <button className="btn-ghost" style={{ padding: "4px 8px" }} onClick={() => handleRejectSubmission(l)}>
                        Отклонить
                      </button>
                    </div>
                  )}
                </li>
              );
            })}
            {clickedDayLeaves.length === 0 && <li className="empty">Никто не в отпуске</li>}
          </ul>
        ) : (
          <ul style={{ margin: "8px 0 0 0", paddingLeft: 20 }}>
            {pendingSubmissions.map((requests) => {
              const first = requests[0];
              const employee = employeesById.get(first.user_id);
              const fullName = employee?.full_name ?? "—";
              const isSelf = first.user_id === currentUser?.id;
              return (
                <li key={first.submission_id ?? first.id} style={{ marginBottom: 10 }}>
                  <button
                    type="button"
                    onClick={() => toggleFocused(first.user_id)}
                    title={`${fullName} — показать все периоды на графике`}
                    style={{
                      display: "block",
                      width: "100%",
                      textAlign: "left",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      background: "none",
                      border: "none",
                      padding: 0,
                      cursor: "pointer",
                      color: focusedEmployeeId === first.user_id ? "var(--accent-ink)" : "inherit",
                      fontWeight: focusedEmployeeId === first.user_id ? 700 : 400,
                    }}
                  >
                    {fullName}
                  </button>
                  {requests.map((r) => (
                    <div key={r.id} className="hint">
                      {format(parseISO(r.date_from), "dd.MM")}
                      {r.date_from !== r.date_to ? `–${format(parseISO(r.date_to), "dd.MM.yyyy")}` : ""}
                    </div>
                  ))}
                  {canApprove && (!isSelf || selfApprovalExempt) && (
                    <div style={{ marginTop: 4 }}>
                      <button className="btn-ghost" style={{ padding: "4px 8px" }} onClick={() => handleApproveSubmission(first)}>
                        Согласовать
                      </button>{" "}
                      <button className="btn-ghost" style={{ padding: "4px 8px" }} onClick={() => handleRejectSubmission(first)}>
                        Отклонить
                      </button>
                    </div>
                  )}
                </li>
              );
            })}
            {pendingSubmissions.length === 0 && <li className="empty">Все заявки согласованы</li>}
          </ul>
        )}
      </div>
      </div>
    </div>
  );
}
