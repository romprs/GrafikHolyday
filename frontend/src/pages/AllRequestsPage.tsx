import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { adminOverrideLeaveRequest, listAllLeaveRequests } from "../api/admin";
import { ApiError } from "../api/client";
import { statusLabel } from "./statusLabel";

export function AllRequestsPage() {
  const queryClient = useQueryClient();
  const { data: requests } = useQuery({ queryKey: ["all-requests"], queryFn: listAllLeaveRequests });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  function startEdit(id: string, currentFrom: string, currentTo: string) {
    setEditingId(id);
    setDateFrom(currentFrom);
    setDateTo(currentTo);
    setReason("");
    setError(null);
  }

  async function handleSave(id: string) {
    setError(null);
    try {
      await adminOverrideLeaveRequest(id, { reason, date_from: dateFrom, date_to: dateTo });
      setEditingId(null);
      queryClient.invalidateQueries({ queryKey: ["all-requests"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось изменить заявку");
    }
  }

  return (
    <div>
      <h3>Все заявки (правка HR)</h3>
      <p style={{ color: "#888", fontSize: "0.9em" }}>
        Правка возможна в любом статусе, требует указания причины — изменение фиксируется в
        журнале.
      </p>
      <table style={{ borderCollapse: "collapse", width: "100%" }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left" }}>Период</th>
            <th style={{ textAlign: "left" }}>Статус</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {requests?.map((r) => (
            <tr key={r.id}>
              {editingId === r.id ? (
                <>
                  <td>
                    <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />{" "}
                    <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
                  </td>
                  <td>{statusLabel(r.status)}</td>
                  <td>
                    <input
                      placeholder="Причина (обязательно)"
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                    />
                    <button onClick={() => handleSave(r.id)} disabled={!reason.trim()}>
                      Сохранить
                    </button>
                    <button onClick={() => setEditingId(null)}>Отмена</button>
                  </td>
                </>
              ) : (
                <>
                  <td>
                    {r.date_from} — {r.date_to} ({r.days} дн.)
                    {r.bonus_requested && " 🎁 доплата"}
                  </td>
                  <td>{statusLabel(r.status)}</td>
                  <td>
                    <button onClick={() => startEdit(r.id, r.date_from, r.date_to)}>
                      Изменить
                    </button>
                  </td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {error && <p style={{ color: "crimson" }}>{error}</p>}
    </div>
  );
}
