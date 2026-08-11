import { useQuery, useQueryClient } from "@tanstack/react-query";
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
import { statusLabel } from "./statusLabel";

function toMatchers(requests: LeaveRequestOut[]): Matcher[] {
  return requests.map((r) => ({ from: parseISO(r.date_from), to: parseISO(r.date_to) }));
}

interface Submission {
  key: string;
  requests: LeaveRequestOut[];
  totalDays: number;
}

function groupBySubmission(requests: LeaveRequestOut[]): Submission[] {
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
  const submissions = groupBySubmission(requests ?? []);

  return (
    <div>
      <h3>Мои заявки</h3>
      {delegationTargets && delegationTargets.length > 0 && (
        <label>
          Чьи заявки показать:{" "}
          <select
            value={onBehalfOf ?? ""}
            onChange={(e) => setOnBehalfOf(e.target.value || undefined)}
          >
            <option value="">Мои</option>
            {delegationTargets.map((t) => (
              <option key={t.id} value={t.id}>
                {t.full_name} ({t.email})
              </option>
            ))}
          </select>
        </label>
      )}
      {balance && (
        <p>
          Баланс {balance.year}: начислено {balance.accrued_days}, использовано{" "}
          {balance.used_days}, остаток <strong>{balance.remaining_days}</strong>
        </p>
      )}

      {(approvedRequests.length > 0 || pendingRequests.length > 0) && (
        <div className="year-grid-picker" style={{ marginBottom: 16 }}>
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
              approved: { backgroundColor: "#c8e6c9", color: "#1b5e20", fontWeight: 600 },
              pending: { backgroundColor: "#fff3cd", color: "#7a5c00", fontWeight: 600 },
            }}
          />
          <div style={{ display: "flex", gap: 16, fontSize: "0.85em", marginTop: 4 }}>
            <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <span
                style={{ width: 12, height: 12, background: "#c8e6c9", display: "inline-block" }}
              />
              согласовано
            </span>
            <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <span
                style={{ width: 12, height: 12, background: "#fff3cd", display: "inline-block" }}
              />
              на согласовании
            </span>
          </div>
        </div>
      )}

      <table style={{ borderCollapse: "collapse", width: "100%" }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left" }}>Периоды</th>
            <th style={{ textAlign: "left" }}>Дней</th>
            <th style={{ textAlign: "left" }}>Статус</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {submissions.map((s) => {
            const status = s.requests[0].status;
            return (
              <tr key={s.key}>
                <td style={{ verticalAlign: "top", padding: "8px 8px 8px 0" }}>
                  {s.requests.map((r) => (
                    <div key={r.id}>
                      {r.date_from} — {r.date_to}
                      {r.bonus_requested && " 🎁"}
                    </div>
                  ))}
                </td>
                <td style={{ verticalAlign: "top" }}>{s.totalDays}</td>
                <td style={{ verticalAlign: "top" }}>{statusLabel(status)}</td>
                <td style={{ verticalAlign: "top" }}>
                  {status === "pending_approval" && (
                    <button onClick={() => handleCancel(s)}>Отменить</button>
                  )}
                  {status === "approved" && (
                    <span style={{ color: "#888", fontSize: "0.85em" }}>
                      Отменить может только руководитель
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
