import { useQuery, useQueryClient } from "@tanstack/react-query";
import { approveLeaveRequest, listPendingForTeam, rejectLeaveRequest } from "../api/leaveRequests";

export function ApprovalQueuePage() {
  const queryClient = useQueryClient();
  const { data: requests } = useQuery({
    queryKey: ["team-pending-requests"],
    queryFn: listPendingForTeam,
  });

  async function handleApprove(id: string) {
    await approveLeaveRequest(id);
    queryClient.invalidateQueries({ queryKey: ["team-pending-requests"] });
  }

  async function handleReject(id: string) {
    await rejectLeaveRequest(id);
    queryClient.invalidateQueries({ queryKey: ["team-pending-requests"] });
  }

  return (
    <div>
      <h3>Заявки на согласование</h3>
      {requests?.length === 0 && <p>Нет заявок, ожидающих согласования.</p>}
      <table style={{ borderCollapse: "collapse", width: "100%" }}>
        <tbody>
          {requests?.map((r) => (
            <tr key={r.id}>
              <td>
                {r.date_from} — {r.date_to} ({r.days} дн.)
                {r.bonus_requested && " 🎁 доплата"}
              </td>
              <td>{r.comment}</td>
              <td>
                <button onClick={() => handleApprove(r.id)}>Согласовать</button>{" "}
                <button onClick={() => handleReject(r.id)}>Отклонить</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
