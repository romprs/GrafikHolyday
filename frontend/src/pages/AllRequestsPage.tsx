import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { adminOverrideLeaveRequest, listAllLeaveRequests } from "../api/admin";
import { apiFetch, ApiError } from "../api/client";
import type { LeaveRequestAdminOut, LeaveRequestStatus, OrgUnitOut } from "../api/types";
import { statusBadgeClass, statusLabel } from "./statusLabel";

const STATUS_OPTIONS: LeaveRequestStatus[] = [
  "draft",
  "pending_approval",
  "approved",
  "rejected",
  "cancelled",
];

interface Submission {
  key: string;
  employeeName: string;
  orgUnitName: string;
  requests: LeaveRequestAdminOut[];
}

function groupBySubmission(requests: LeaveRequestAdminOut[]): Submission[] {
  const groups = new Map<string, LeaveRequestAdminOut[]>();
  for (const r of requests) {
    // submission_id может быть пустым у заявок, созданных до появления
    // группировки — тогда такая заявка просто образует группу из одного периода.
    const key = r.submission_id ?? r.id;
    const list = groups.get(key) ?? [];
    list.push(r);
    groups.set(key, list);
  }
  return Array.from(groups.entries()).map(([key, group]) => ({
    key,
    employeeName: group[0].user_full_name,
    orgUnitName: group[0].org_unit_name ?? "—",
    requests: group.sort((a, b) => a.date_from.localeCompare(b.date_from)),
  }));
}

export function AllRequestsPage() {
  const queryClient = useQueryClient();
  const { data: requests } = useQuery({ queryKey: ["all-requests"], queryFn: listAllLeaveRequests });
  const { data: orgUnits } = useQuery({
    queryKey: ["org-units"],
    queryFn: () => apiFetch<OrgUnitOut[]>("/org-units"),
  });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [bonusRequested, setBonusRequested] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const [nameFilter, setNameFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<LeaveRequestStatus | "">("");
  const [orgUnitFilter, setOrgUnitFilter] = useState("");
  // По умолчанию выключено — раньше фильтр по подразделению всегда был
  // точным совпадением, и HR-admin не мог одним выбором посмотреть заявки
  // всего вышестоящего подразделения вместе со всеми вложенными в него.
  const [includeSubunits, setIncludeSubunits] = useState(false);

  // Все подразделения, вложенные в выбранное (включая его самого) — по
  // parent_id, без обращения к бэкенду (список подразделений уже загружен).
  const orgUnitFilterIds = useMemo(() => {
    if (!orgUnitFilter || !includeSubunits) return null;
    const units = orgUnits ?? [];
    const ids = new Set<string>([orgUnitFilter]);
    let added = true;
    while (added) {
      added = false;
      for (const u of units) {
        if (u.parent_id && ids.has(u.parent_id) && !ids.has(u.id)) {
          ids.add(u.id);
          added = true;
        }
      }
    }
    return ids;
  }, [orgUnits, orgUnitFilter, includeSubunits]);

  const filteredRequests = useMemo(() => {
    return (requests ?? []).filter((r) => {
      if (nameFilter && !r.user_full_name.toLowerCase().includes(nameFilter.toLowerCase())) {
        return false;
      }
      if (statusFilter && r.status !== statusFilter) return false;
      if (orgUnitFilter) {
        if (orgUnitFilterIds) {
          if (!r.org_unit_id || !orgUnitFilterIds.has(r.org_unit_id)) return false;
        } else if (r.org_unit_id !== orgUnitFilter) {
          return false;
        }
      }
      return true;
    });
  }, [requests, nameFilter, statusFilter, orgUnitFilter, orgUnitFilterIds]);

  const submissions = useMemo(() => groupBySubmission(filteredRequests), [filteredRequests]);

  function startEdit(id: string, currentFrom: string, currentTo: string, currentBonus: boolean) {
    setEditingId(id);
    setDateFrom(currentFrom);
    setDateTo(currentTo);
    setBonusRequested(currentBonus);
    setReason("");
    setError(null);
  }

  async function handleSave(id: string) {
    setError(null);
    try {
      await adminOverrideLeaveRequest(id, {
        reason,
        date_from: dateFrom,
        date_to: dateTo,
        bonus_requested: bonusRequested,
      });
      setEditingId(null);
      queryClient.invalidateQueries({ queryKey: ["all-requests"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось изменить заявку");
    }
  }

  async function handleCancel(id: string) {
    const cancelReason = window.prompt("Причина отмены заявки целиком — все периоды (обязательно):");
    if (!cancelReason || !cancelReason.trim()) return;
    setError(null);
    try {
      // Заявка одна на все периоды (согласуется целиком) — отменяется тоже
      // целиком; править даты/ЕСВ по-прежнему можно по одному периоду.
      await adminOverrideLeaveRequest(id, {
        reason: cancelReason,
        status: "cancelled",
        whole_submission: true,
      });
      queryClient.invalidateQueries({ queryKey: ["all-requests"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось отменить заявку");
    }
  }

  return (
    <div>
      <h3>Все заявки (правка HR)</h3>
      <p className="hint">
        Правка возможна в любом статусе, требует указания причины — изменение фиксируется в
        журнале.
      </p>

      <div className="toolbar">
        <input
          type="text"
          placeholder="Поиск по ФИО"
          value={nameFilter}
          onChange={(e) => setNameFilter(e.target.value)}
          style={{ width: 200 }}
        />
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as LeaveRequestStatus | "")}>
          <option value="">Все статусы</option>
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {statusLabel(s)}
            </option>
          ))}
        </select>
        <select value={orgUnitFilter} onChange={(e) => setOrgUnitFilter(e.target.value)}>
          <option value="">Все подразделения</option>
          {(orgUnits ?? []).map((u) => (
            <option key={u.id} value={u.id}>
              {u.name}
            </option>
          ))}
        </select>
        <label style={{ opacity: orgUnitFilter ? 1 : 0.5, display: "flex", alignItems: "center", gap: 6 }}>
          <input
            type="checkbox"
            checked={includeSubunits}
            disabled={!orgUnitFilter}
            onChange={(e) => setIncludeSubunits(e.target.checked)}
          />
          с вложенными подразделениями
        </label>
        <span className="hint">
          Показано {filteredRequests.length} из {requests?.length ?? 0}
        </span>
      </div>

      <div className="panel">
        <table className="t">
          <thead>
            <tr>
              <th>Сотрудник</th>
              <th>Подразделение</th>
              <th>Периоды заявки</th>
            </tr>
          </thead>
          <tbody>
            {submissions.map((s) => (
              <tr key={s.key}>
                <td style={{ fontWeight: 700, verticalAlign: "top" }}>
                  {s.employeeName}
                  {s.requests.some((r) => r.status !== "cancelled") && (
                    <div>
                      <button
                        className="btn-ghost"
                        style={{ padding: "4px 0", fontWeight: 700 }}
                        onClick={() => handleCancel(s.requests.find((r) => r.status !== "cancelled")!.id)}
                      >
                        Отменить заявку
                      </button>
                    </div>
                  )}
                </td>
                <td style={{ verticalAlign: "top" }}>{s.orgUnitName}</td>
                <td>
                  {s.requests.map((r) => (
                    <div
                      key={r.id}
                      style={{
                        display: "flex",
                        alignItems: "flex-start",
                        justifyContent: "space-between",
                        gap: 12,
                        padding: "6px 0",
                        borderBottom: "1px solid var(--hairline)",
                      }}
                    >
                      {editingId === r.id ? (
                        <>
                          <div>
                            <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />{" "}
                            <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
                            <label style={{ display: "block", marginTop: 4, fontSize: "0.85em" }}>
                              <input
                                type="checkbox"
                                checked={bonusRequested}
                                onChange={(e) => setBonusRequested(e.target.checked)}
                              />{" "}
                              🎁 выплата ЕСВ
                            </label>
                            <input
                              placeholder="Причина (обязательно)"
                              value={reason}
                              onChange={(e) => setReason(e.target.value)}
                              style={{ marginTop: 4 }}
                            />
                          </div>
                          <div style={{ whiteSpace: "nowrap" }}>
                            <button
                              className="btn-primary"
                              onClick={() => handleSave(r.id)}
                              disabled={!reason.trim()}
                            >
                              Сохранить
                            </button>{" "}
                            <button className="btn-ghost" onClick={() => setEditingId(null)}>
                              Отмена
                            </button>
                          </div>
                        </>
                      ) : (
                        <>
                          <div>
                            {r.date_from} — {r.date_to} ({r.days} дн.)
                            {r.bonus_requested && " 🎁 выплата ЕСВ"}{" "}
                            <span className={`badge ${statusBadgeClass(r.status)}`}>
                              {statusLabel(r.status)}
                            </span>
                          </div>
                          <div style={{ whiteSpace: "nowrap" }}>
                            <button
                              className="btn-ghost"
                              onClick={() => startEdit(r.id, r.date_from, r.date_to, r.bonus_requested)}
                            >
                              Изменить
                            </button>{" "}
                          </div>
                        </>
                      )}
                    </div>
                  ))}
                </td>
              </tr>
            ))}
            {submissions.length === 0 && (
              <tr>
                <td colSpan={3} className="empty">
                  Ничего не найдено.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {error && <p className="error-text">{error}</p>}
    </div>
  );
}
