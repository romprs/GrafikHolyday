import { useQuery, useQueryClient } from "@tanstack/react-query";
import { differenceInCalendarDays, format } from "date-fns";
import { useState } from "react";
import type { DateRange } from "react-day-picker";
import { ApiError } from "../api/client";
import { getBlockedRanges, getRestrictionSettings } from "../api/calendar";
import { createLeaveRequestsBulk, getMyBalance } from "../api/leaveRequests";
import { DateRangePicker } from "../components/DateRangePicker";

function toIsoDate(d: Date): string {
  return format(d, "yyyy-MM-dd");
}

interface PlannedPeriod {
  id: string;
  dateFrom: string;
  dateTo: string;
  comment: string;
  days: number;
}

export function RequestFormPage() {
  const queryClient = useQueryClient();
  const [range, setRange] = useState<DateRange | undefined>();
  const [comment, setComment] = useState("");
  const [periods, setPeriods] = useState<PlannedPeriod[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const { data: blockedRanges } = useQuery({
    queryKey: ["blocked-ranges"],
    queryFn: getBlockedRanges,
  });
  const { data: restrictionSettings } = useQuery({
    queryKey: ["restriction-settings"],
    queryFn: getRestrictionSettings,
  });
  const { data: balance } = useQuery({
    queryKey: ["my-balance"],
    queryFn: getMyBalance,
  });

  const minDaysSetting = restrictionSettings?.find((s) => s.key === "min_leave_duration");
  const minDays =
    minDaysSetting?.enabled && typeof minDaysSetting.params.min_days === "number"
      ? minDaysSetting.params.min_days
      : 1;

  const planningYearSetting = restrictionSettings?.find((s) => s.key === "planning_year");
  const planningYear =
    typeof planningYearSetting?.params.year === "number"
      ? planningYearSetting.params.year
      : new Date().getFullYear();

  const currentRangeDays =
    range?.from && range?.to ? differenceInCalendarDays(range.to, range.from) + 1 : null;
  const canAddPeriod = currentRangeDays !== null && currentRangeDays >= minDays;

  const plannedTotalDays = periods.reduce((sum, p) => sum + p.days, 0);
  const remainingAfterPlanned =
    balance !== undefined ? balance.remaining_days - plannedTotalDays : null;

  // Уже добавленные в список периоды тоже нельзя выбрать повторно —
  // показываем их в пикере как занятые, наравне с недоступными периодами.
  const rangesWithPlanned = [
    ...(blockedRanges ?? []),
    ...periods.map((p) => ({
      date_from: p.dateFrom,
      date_to: p.dateTo,
      reason: "Уже добавлено в эту заявку",
    })),
  ];

  function handleAddPeriod() {
    if (!range?.from || !range?.to || currentRangeDays === null) return;
    setPeriods([
      ...periods,
      {
        id: crypto.randomUUID(),
        dateFrom: toIsoDate(range.from),
        dateTo: toIsoDate(range.to),
        comment,
        days: currentRangeDays,
      },
    ]);
    setRange(undefined);
    setComment("");
  }

  function handleRemovePeriod(id: string) {
    setPeriods(periods.filter((p) => p.id !== id));
  }

  async function handleSubmitAll() {
    if (periods.length === 0) return;
    setError(null);
    setSuccess(false);
    setSubmitting(true);
    try {
      await createLeaveRequestsBulk(
        periods.map((p) => ({ date_from: p.dateFrom, date_to: p.dateTo, comment: p.comment })),
      );
      setSuccess(true);
      setPeriods([]);
      queryClient.invalidateQueries({ queryKey: ["my-leave-requests"] });
      queryClient.invalidateQueries({ queryKey: ["my-balance"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось отправить заявку");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <h3>Новая заявка на отпуск</h3>

      {balance && (
        <p>
          Баланс {balance.year}: начислено {balance.accrued_days}, использовано{" "}
          {balance.used_days}, остаток <strong>{balance.remaining_days}</strong> дн.
          {periods.length > 0 && remainingAfterPlanned !== null && (
            <>
              {" "}
              — выбрано в заявке {plannedTotalDays} дн., после отправки останется{" "}
              <strong>{remainingAfterPlanned}</strong> дн.
            </>
          )}
        </p>
      )}

      <DateRangePicker
        range={range}
        onChange={setRange}
        blockedRanges={rangesWithPlanned}
        minDays={minDays}
        year={planningYear}
      />
      <label>
        Комментарий к периоду
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          style={{ display: "block", width: "100%" }}
        />
      </label>
      <button type="button" onClick={handleAddPeriod} disabled={!canAddPeriod}>
        Добавить период в заявку
      </button>

      {periods.length > 0 && (
        <div>
          <h4>Периоды в заявке</h4>
          <table style={{ borderCollapse: "collapse", width: "100%" }}>
            <tbody>
              {periods.map((p) => (
                <tr key={p.id}>
                  <td>
                    {p.dateFrom} — {p.dateTo} ({p.days} дн.)
                  </td>
                  <td>{p.comment}</td>
                  <td>
                    <button type="button" onClick={() => handleRemovePeriod(p.id)}>
                      Убрать
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <button type="button" onClick={handleSubmitAll} disabled={submitting}>
            Отправить {periods.length > 1 ? `все периоды (${periods.length})` : "заявку"} на
            согласование
          </button>
        </div>
      )}

      {error && <p style={{ color: "crimson" }}>{error}</p>}
      {success && <p style={{ color: "green" }}>Заявка(и) отправлена(ы) на согласование.</p>}
    </div>
  );
}
