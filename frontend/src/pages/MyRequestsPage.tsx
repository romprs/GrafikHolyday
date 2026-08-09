import { useQuery, useQueryClient } from "@tanstack/react-query";
import { parseISO } from "date-fns";
import { ru } from "date-fns/locale/ru";
import { DayPicker, type Matcher } from "react-day-picker";
import "react-day-picker/style.css";
import "../components/DateRangePicker.css";
import { getRestrictionSettings } from "../api/calendar";
import { cancelLeaveRequest, getMyBalance, listMyLeaveRequests } from "../api/leaveRequests";
import type { LeaveRequestOut } from "../api/types";
import { statusLabel } from "./statusLabel";

function toMatchers(requests: LeaveRequestOut[]): Matcher[] {
  return requests.map((r) => ({ from: parseISO(r.date_from), to: parseISO(r.date_to) }));
}

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
  const { data: restrictionSettings } = useQuery({
    queryKey: ["restriction-settings"],
    queryFn: getRestrictionSettings,
  });

  const planningYearSetting = restrictionSettings?.find((s) => s.key === "planning_year");
  const planningYear =
    typeof planningYearSetting?.params.year === "number"
      ? planningYearSetting.params.year
      : new Date().getFullYear();

  async function handleCancel(id: string) {
    await cancelLeaveRequest(id);
    queryClient.invalidateQueries({ queryKey: ["my-leave-requests"] });
    queryClient.invalidateQueries({ queryKey: ["my-balance"] });
  }

  const approvedRequests = (requests ?? []).filter((r) => r.status === "approved");
  const pendingRequests = (requests ?? []).filter((r) => r.status === "pending_approval");

  return (
    <div>
      <h3>Мои заявки</h3>
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
                {r.status === "pending_approval" && (
                  <button onClick={() => handleCancel(r.id)}>Отменить</button>
                )}
                {r.status === "approved" && (
                  <span style={{ color: "#888", fontSize: "0.85em" }}>
                    Отменить может только руководитель
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
