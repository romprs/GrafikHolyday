import { useQuery, useQueryClient } from "@tanstack/react-query";
import { cancelLeaveRequest, getMyBalance, listMyLeaveRequests } from "../api/leaveRequests";
import { statusLabel } from "./statusLabel";

export function MyRequestsPage() {
  const queryClient = useQueryClient();
  const { data: requests } = useQuery({
    queryKey: ["my-leave-requests"],
    queryFn: listMyLeaveRequests,
  });
  const { data: balance } = useQuery({
    queryKey: ["my-balance"],
    queryFn: getMyBalance,
  });

  async function handleCancel(id: string) {
    await cancelLeaveRequest(id);
    queryClient.invalidateQueries({ queryKey: ["my-leave-requests"] });
    queryClient.invalidateQueries({ queryKey: ["my-balance"] });
  }

  return (
    <div>
      <h3>Мои заявки</h3>
      {balance && (
        <p>
          Баланс {balance.year}: начислено {balance.accrued_days}, использовано{" "}
          {balance.used_days}, остаток <strong>{balance.remaining_days}</strong>
        </p>
      )}
      <table style={{ borderCollapse: "collapse", width: "100%" }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left" }}>Период</th>
            <th style={{ textAlign: "left" }}>Дней</th>
            <th style={{ textAlign: "left" }}>Статус</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {requests?.map((r) => (
            <tr key={r.id}>
              <td>
                {r.date_from} — {r.date_to}
                {r.bonus_requested && " 🎁"}
              </td>
              <td>{r.days}</td>
              <td>{statusLabel(r.status)}</td>
              <td>
                {(r.status === "pending_approval" || r.status === "approved") && (
                  <button onClick={() => handleCancel(r.id)}>Отменить</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
