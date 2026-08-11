import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import {
  approveLeaveRequest,
  listApprovedForTeam,
  listPendingForTeam,
  managerCancelLeaveRequest,
  rejectLeaveRequest,
} from "../api/leaveRequests";
import type { LeaveRequestWithEmployeeOut } from "../api/types";

interface Submission {
  key: string;
  employeeName: string;
  requests: LeaveRequestWithEmployeeOut[];
  totalDays: number;
}

function groupBySubmission(requests: LeaveRequestWithEmployeeOut[]): Submission[] {
  const groups = new Map<string, LeaveRequestWithEmployeeOut[]>();
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
    requests: group.sort((a, b) => a.date_from.localeCompare(b.date_from)),
    totalDays: group.reduce((sum, r) => sum + r.days, 0),
  }));
}

export function ApprovalQueuePage() {
  const queryClient = useQueryClient();
  const { data: pending } = useQuery({
    queryKey: ["team-pending-requests"],
    queryFn: listPendingForTeam,
  });
  const { data: approved } = useQuery({
    queryKey: ["team-approved-requests"],
    queryFn: listApprovedForTeam,
  });

  const pendingSubmissions = useMemo(() => groupBySubmission(pending ?? []), [pending]);
  const approvedSubmissions = useMemo(() => groupBySubmission(approved ?? []), [approved]);

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ["team-pending-requests"] });
    queryClient.invalidateQueries({ queryKey: ["team-approved-requests"] });
  }

  // Один API-вызов на любой period из группы — бэкенд согласует/отклоняет/
  // отменяет всю заявку (все её периоды с тем же submission_id) атомарно.
  async function handleApprove(submission: Submission) {
    await approveLeaveRequest(submission.requests[0].id);
    invalidate();
  }

  async function handleReject(submission: Submission) {
    await rejectLeaveRequest(submission.requests[0].id);
    invalidate();
  }

  async function handleManagerCancel(submission: Submission) {
    await managerCancelLeaveRequest(submission.requests[0].id);
    invalidate();
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div>
        <h3>Заявки на согласование</h3>
        {pendingSubmissions.length === 0 && <p>Нет заявок, ожидающих согласования.</p>}
        <table style={{ borderCollapse: "collapse", width: "100%" }}>
          <tbody>
            {pendingSubmissions.map((s) => (
              <tr key={s.key}>
                <td style={{ verticalAlign: "top", padding: "8px 8px 8px 0", fontWeight: 600 }}>
                  {s.employeeName}
                </td>
                <td style={{ verticalAlign: "top", padding: "8px 8px 8px 0" }}>
                  {s.requests.map((r) => (
                    <div key={r.id}>
                      {r.date_from} — {r.date_to} ({r.days} дн.)
                      {r.bonus_requested && " 🎁 доплата"}
                    </div>
                  ))}
                  {s.requests.length > 1 && (
                    <div style={{ color: "#888", fontSize: "0.85em" }}>
                      Итого {s.requests.length} период(а/ов), {s.totalDays} дн.
                    </div>
                  )}
                </td>
                <td style={{ verticalAlign: "top" }}>
                  <button onClick={() => handleApprove(s)}>Согласовать</button>{" "}
                  <button onClick={() => handleReject(s)}>Отклонить</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div>
        <h3>Согласованные заявки моих сотрудников</h3>
        <p style={{ color: "#888", fontSize: "0.85em" }}>
          Сотрудник сам отменить уже согласованную заявку не может — только руководитель.
        </p>
        {approvedSubmissions.length === 0 && <p>Нет согласованных заявок.</p>}
        <table style={{ borderCollapse: "collapse", width: "100%" }}>
          <tbody>
            {approvedSubmissions.map((s) => (
              <tr key={s.key}>
                <td style={{ verticalAlign: "top", padding: "8px 8px 8px 0", fontWeight: 600 }}>
                  {s.employeeName}
                </td>
                <td style={{ verticalAlign: "top", padding: "8px 8px 8px 0" }}>
                  {s.requests.map((r) => (
                    <div key={r.id}>
                      {r.date_from} — {r.date_to} ({r.days} дн.)
                      {r.bonus_requested && " 🎁 доплата"}
                    </div>
                  ))}
                </td>
                <td style={{ verticalAlign: "top" }}>
                  <button onClick={() => handleManagerCancel(s)}>Отменить</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
