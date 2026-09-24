import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { parseISO } from "date-fns";
import { ru } from "date-fns/locale/ru";
import { useState } from "react";
import { DayPicker, type Matcher } from "react-day-picker";
import "react-day-picker/style.css";
import "../components/DateRangePicker.css";
import { getRestrictionSettings } from "../api/calendar";
import { listMyDelegationTargets } from "../api/delegations";
import { cancelLeaveRequest, getMyBalance, listMyLeaveRequests } from "../api/leaveRequests";
import type { LeaveRequestOut } from "../api/types";
import { statusBadgeClass, statusLabel } from "./statusLabel";

function toMatchers(requests: LeaveRequestOut[]): Matcher[] {
  return requests.map((r) => ({ from: parseISO(r.date_from), to: parseISO(r.date_to) }));
}

interface Submission {
  key: string;
  requests: LeaveRequestOut[];
  totalDays: number;
  ownerName?: string;
}

function groupBySubmission(requests: LeaveRequestOut[], ownerName?: string): Submission[] {
  const groups = new Map<string, LeaveRequestOut[]>();
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
    requests: group.sort((a, b) => a.date_from.localeCompare(b.date_from)),
    totalDays: group.reduce((sum, r) => sum + r.days, 0),
    ownerName,
  }));
}

export function MyRequestsPage() {
  const queryClient = useQueryClient();
  const [onBehalfOf, setOnBehalfOf] = useState<string | undefined>(undefined);
  const { data: delegationTargets } = useQuery({
    queryKey: ["delegation-targets"],
    queryFn: listMyDelegationTargets,
  });
  const { data: requests } = useQuery({
    queryKey: ["my-leave-requests", onBehalfOf],
    queryFn: () => listMyLeaveRequests(onBehalfOf),
  });
  // Заявки, поданные текущим пользователем за подопечных по делегированию —
  // показываем их прямо в «Мои заявки» (а не только при переключении
  // селектора на конкретного подопечного): раз их подал я, я должен видеть
  // их здесь, не переключаясь каждый раз на чужое имя.
  const delegateRequestQueries = useQueries({
    queries: (delegationTargets ?? []).map((t) => ({
      queryKey: ["my-leave-requests", t.id],
      queryFn: () => listMyLeaveRequests(t.id),
    })),
  });
  const { data: balance } = useQuery({
    queryKey: ["my-balance", onBehalfOf],
    queryFn: () => getMyBalance(onBehalfOf),
  });
  const { data: restrictionSettings } = useQuery({
    queryKey: ["restriction-settings"],
    queryFn: getRestrictionSettings,
  });

  const planningYearSetting = restrictionSettings?.find((s) => s.key === "planning_year");
  const planningYear =
    typeof planningYearSetting?.params.year === "number"
      ? planningYearSetting.params.year
      : new Date().getFullYear();

  // Один вызов — бэкенд отменяет всю заявку (все периоды с тем же
  // submission_id) атомарно, не только переданный период.
  async function handleCancel(submission: Submission) {
    await cancelLeaveRequest(submission.requests[0].id);
    queryClient.invalidateQueries({ queryKey: ["my-leave-requests"] });
    queryClient.invalidateQueries({ queryKey: ["my-balance"] });
  }

  const approvedRequests = (requests ?? []).filter((r) => r.status === "approved");
  const pendingRequests = (requests ?? []).filter((r) => r.status === "pending_approval");

  // В таблице снизу — свои заявки и, только пока выбрано «Мои» (а не
  // конкретный подопечный в селекторе выше), ещё и все заявки, поданные за
  // подопечных: календарь и карточки баланса выше по-прежнему про одного
  // конкретного человека (себя), а таблица — свод всего, что я подал.
  const showMergedDelegated = onBehalfOf === undefined && (delegationTargets?.length ?? 0) > 0;
  const submissions = showMergedDelegated
    ? [
        ...groupBySubmission(requests ?? []),
        ...(delegationTargets ?? []).flatMap((t, i) =>
          groupBySubmission(delegateRequestQueries[i]?.data ?? [], t.full_name),
        ),
      ]
    : groupBySubmission(requests ?? []);

  return (
    <div>
      <h3>Мои заявки</h3>

      {delegationTargets && delegationTargets.length > 0 && (
        <div className="fieldrow">
          <div className="field" style={{ maxWidth: 320 }}>
            <label>Чьи заявки показать</label>
            <select value={onBehalfOf ?? ""} onChange={(e) => setOnBehalfOf(e.target.value || undefined)}>
              <option value="">Мои</option>
              {delegationTargets.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.full_name} ({t.email})
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      {balance && (
        <div className="cards">
          <div className="card">
            <div className="n">{balance.accrued_days}</div>
            <div className="l">начислено, {balance.year}</div>
          </div>
          <div className="card">
            <div className="n">{balance.used_days}</div>
            <div className="l">использовано</div>
          </div>
          <div className="card">
            <div className="n">{balance.remaining_days}</div>
            <div className="l">остаток</div>
          </div>
        </div>
      )}

      {(approvedRequests.length > 0 || pendingRequests.length > 0) && (
        <div className="panel year-grid-picker">
          <DayPicker
            key={planningYear}
            locale={ru}
            numberOfMonths={12}
            defaultMonth={new Date(planningYear, 0, 1)}
            disableNavigation
            hideNavigation
            modifiers={{
              approved: toMatchers(approvedRequests),
              pending: toMatchers(pendingRequests),
            }}
            modifiersStyles={{
              approved: { backgroundColor: "var(--ok-bg)", color: "var(--ok-fg)", fontWeight: 600 },
              pending: { backgroundColor: "var(--wait-bg)", color: "var(--wait-fg)", fontWeight: 600 },
            }}
          />
          <div style={{ display: "flex", gap: 16, fontSize: "0.85em", marginTop: 4 }}>
            <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <span className="badge ok" style={{ width: 10, height: 10, padding: 0, borderRadius: 3 }} />
              согласовано
            </span>
            <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <span className="badge wait" style={{ width: 10, height: 10, padding: 0, borderRadius: 3 }} />
              на согласовании
            </span>
          </div>
        </div>
      )}

      <div className="panel">
        <table className="t">
          <thead>
            <tr>
              {showMergedDelegated && <th>Сотрудник</th>}
              <th>Периоды</th>
              <th>Дней</th>
              <th>Статус</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {submissions.map((s) => {
              const status = s.requests[0].status;
              return (
                <tr key={s.key}>
                  {showMergedDelegated && <td>{s.ownerName ?? "Я"}</td>}
                  <td>
                    {s.requests.map((r) => (
                      <div key={r.id}>
                        {r.date_from} — {r.date_to}
                        {r.bonus_requested && " 🎁"}
                      </div>
                    ))}
                  </td>
                  <td>{s.totalDays}</td>
                  <td>
                    <span className={`badge ${statusBadgeClass(status)}`}>{statusLabel(status)}</span>
                  </td>
                  <td>
                    {status === "pending_approval" && (
                      <button type="button" className="btn-ghost" onClick={() => handleCancel(s)}>
                        Отменить
                      </button>
                    )}
                    {status === "approved" && <span className="hint">Отменить может только руководитель</span>}
                  </td>
                </tr>
              );
            })}
            {submissions.length === 0 && (
              <tr>
                <td colSpan={showMergedDelegated ? 5 : 4} className="empty">
                  Заявок пока нет.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
