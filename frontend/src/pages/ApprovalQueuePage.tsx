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
    <div>
      <h3>Заявки на согласование</h3>
      <div className="panel">
        {pendingSubmissions.length === 0 && <p className="empty">Нет заявок, ожидающих согласования.</p>}
        {pendingSubmissions.length > 0 && (
          <table className="t">
            <tbody>
              {pendingSubmissions.map((s) => (
                <tr key={s.key}>
                  <td style={{ fontWeight: 700 }}>{s.employeeName}</td>
                  <td>
                    {s.requests.map((r) => (
                      <div key={r.id}>
                        {r.date_from} — {r.date_to} ({r.days} дн.)
                        {r.bonus_requested && " 🎁 выплата ЕСВ"}
                      </div>
                    ))}
                    {s.requests.length > 1 && (
                      <div className="hint">
                        Итого {s.requests.length} период(а/ов), {s.totalDays} дн.
                      </div>
                    )}
                  </td>
                  <td>
                    <button className="btn-ghost" onClick={() => handleReject(s)}>
                      Отклонить
                    </button>{" "}
                    <button className="btn-primary" onClick={() => handleApprove(s)}>
                      Согласовать
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <h3>Согласованные заявки моих сотрудников</h3>
      <p className="hint" style={{ marginBottom: 10 }}>
        Сотрудник сам отменить уже согласованную заявку не может — только руководитель.
      </p>
      <div className="panel">
        {approvedSubmissions.length === 0 && <p className="empty">Нет согласованных заявок.</p>}
        {approvedSubmissions.length > 0 && (
          <table className="t">
            <tbody>
              {approvedSubmissions.map((s) => (
                <tr key={s.key}>
                  <td style={{ fontWeight: 700 }}>{s.employeeName}</td>
                  <td>
                    {s.requests.map((r) => (
                      <div key={r.id}>
                        {r.date_from} — {r.date_to} ({r.days} дн.)
                        {r.bonus_requested && " 🎁 выплата ЕСВ"}
                      </div>
                    ))}
                  </td>
                  <td>
                    <button className="btn-ghost" onClick={() => handleManagerCancel(s)}>
                      Отменить
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
