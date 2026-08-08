import { useQuery, useQueryClient } from "@tanstack/react-query";
import { differenceInCalendarDays, format } from "date-fns";
import { useState } from "react";
import type { DateRange } from "react-day-picker";
import { ApiError } from "../api/client";
import { getBlockedRanges, getRestrictionSettings } from "../api/calendar";
import { createLeaveRequest } from "../api/leaveRequests";
import { DateRangePicker } from "../components/DateRangePicker";

function toIsoDate(d: Date): string {
  return format(d, "yyyy-MM-dd");
}

export function RequestFormPage() {
  const queryClient = useQueryClient();
  const [range, setRange] = useState<DateRange | undefined>();
  const [comment, setComment] = useState("");
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

  const minDaysSetting = restrictionSettings?.find((s) => s.key === "min_leave_duration");
  const minDays =
    minDaysSetting?.enabled && typeof minDaysSetting.params.min_days === "number"
      ? minDaysSetting.params.min_days
      : 1;

  const days =
    range?.from && range?.to ? differenceInCalendarDays(range.to, range.from) + 1 : null;
  const canSubmit = days !== null && days >= minDays;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!range?.from || !range?.to) return;
    setError(null);
    setSuccess(false);
    setSubmitting(true);
    try {
      await createLeaveRequest({
        date_from: toIsoDate(range.from),
        date_to: toIsoDate(range.to),
        comment,
      });
      setSuccess(true);
      setRange(undefined);
      setComment("");
      queryClient.invalidateQueries({ queryKey: ["my-leave-requests"] });
      queryClient.invalidateQueries({ queryKey: ["my-balance"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось отправить заявку");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <h3>Новая заявка на отпуск</h3>
      <DateRangePicker
        range={range}
        onChange={setRange}
        blockedRanges={blockedRanges ?? []}
        minDays={minDays}
      />
      <label>
        Комментарий
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          style={{ display: "block", width: "100%" }}
        />
      </label>
      <button type="submit" disabled={submitting || !canSubmit}>
        Отправить
      </button>
      {error && <p style={{ color: "crimson" }}>{error}</p>}
      {success && <p style={{ color: "green" }}>Заявка отправлена на согласование.</p>}
    </form>
  );
}
