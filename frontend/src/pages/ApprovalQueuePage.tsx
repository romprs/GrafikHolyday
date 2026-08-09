import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { approveLeaveRequest, listPendingForTeam, rejectLeaveRequest } from "../api/leaveRequests";
import type { LeaveRequestOut } from "../api/types";

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

export function ApprovalQueuePage() {
  const queryClient = useQueryClient();
  const { data: requests } = useQuery({
    queryKey: ["team-pending-requests"],
    queryFn: listPendingForTeam,
  });

  const submissions = useMemo(() => groupBySubmission(requests ?? []), [requests]);

  async function handleApprove(submission: Submission) {
    await Promise.all(submission.requests.map((r) => approveLeaveRequest(r.id)));
    queryClient.invalidateQueries({ queryKey: ["team-pending-requests"] });
  }

  async function handleReject(submission: Submission) {
    await Promise.all(submission.requests.map((r) => rejectLeaveRequest(r.id)));
    queryClient.invalidateQueries({ queryKey: ["team-pending-requests"] });
  }

  return (
    <div>
      <h3>Заявки на согласование</h3>
      {submissions.length === 0 && <p>Нет заявок, ожидающих согласования.</p>}
      <table style={{ borderCollapse: "collapse", width: "100%" }}>
        <tbody>
          {submissions.map((s) => (
            <tr key={s.key}>
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
  );
}
