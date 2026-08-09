import { useQuery, useQueryClient } from "@tanstack/react-query";
import { differenceInCalendarDays, format } from "date-fns";
import { useState } from "react";
import type { DateRange } from "react-day-picker";
import { ApiError } from "../api/client";
import { getBlockedRanges, getRestrictionSettings } from "../api/calendar";
import { addDraft, getMyBalance, listDrafts, removeDraft, submitDrafts } from "../api/leaveRequests";
import { DateRangePicker } from "../components/DateRangePicker";

function toIsoDate(d: Date): string {
  return format(d, "yyyy-MM-dd");
}

export function RequestFormPage() {
  const queryClient = useQueryClient();
  const [range, setRange] = useState<DateRange | undefined>();
  const [comment, setComment] = useState("");
  const [bonusRequested, setBonusRequested] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [adding, setAdding] = useState(false);
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

  const planningYearSetting = restrictionSettings?.find((s) => s.key === "planning_year");
  const planningYear =
    typeof planningYearSetting?.params.year === "number"
      ? planningYearSetting.params.year
      : new Date().getFullYear();

  const { data: drafts, isLoading: draftsLoading } = useQuery({
    queryKey: ["drafts", planningYear],
    queryFn: () => listDrafts(planningYear),
  });

  const minDaysSetting = restrictionSettings?.find((s) => s.key === "min_leave_duration");
  const minDays =
    minDaysSetting?.enabled && typeof minDaysSetting.params.min_days === "number"
      ? minDaysSetting.params.min_days
      : 1;

  const bonusSetting = restrictionSettings?.find((s) => s.key === "vacation_bonus");
  const bonusMinDays =
    typeof bonusSetting?.params.min_days === "number" ? bonusSetting.params.min_days : 14;
  const bonusProgramEnabled = bonusSetting?.enabled ?? false;

  const currentRangeDays =
    range?.from && range?.to ? differenceInCalendarDays(range.to, range.from) + 1 : null;
  const canAddPeriod = currentRangeDays !== null && currentRangeDays >= minDays;
  const qualifiesForBonus = currentRangeDays !== null && currentRangeDays > bonusMinDays;

  const plannedTotalDays = (drafts ?? []).reduce((sum, p) => sum + p.days, 0);
  const remainingAfterPlanned =
    balance !== undefined ? balance.remaining_days - plannedTotalDays : null;
  const readyToSubmit =
    (drafts?.length ?? 0) > 0 && remainingAfterPlanned !== null && remainingAfterPlanned === 0;

  const plannedRanges = (drafts ?? []).map((d) => ({
    date_from: d.date_from,
    date_to: d.date_to,
    reason: "Уже добавлено в эту заявку",
  }));

  function clearSelection() {
    setRange(undefined);
    setComment("");
    setBonusRequested(false);
  }

  async function handleAddPeriod() {
    if (!range?.from || !range?.to || currentRangeDays === null) return;
    setError(null);
    setSuccess(false);
    setAdding(true);
    try {
      await addDraft({
        date_from: toIsoDate(range.from),
        date_to: toIsoDate(range.to),
        comment: comment || undefined,
        bonus_requested: bonusRequested && qualifiesForBonus,
      });
      clearSelection();
      queryClient.invalidateQueries({ queryKey: ["drafts"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось добавить период");
    } finally {
      setAdding(false);
    }
  }

  async function handleRemovePeriod(id: string) {
    setError(null);
    try {
      await removeDraft(id);
      queryClient.invalidateQueries({ queryKey: ["drafts"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось убрать период");
    }
  }

  async function handleSubmitAll() {
    if (!drafts || drafts.length === 0) return;
    setError(null);
    setSuccess(false);
    setSubmitting(true);
    try {
      await submitDrafts(planningYear);
      setSuccess(true);
      queryClient.invalidateQueries({ queryKey: ["drafts"] });
      queryClient.invalidateQueries({ queryKey: ["my-leave-requests"] });
      queryClient.invalidateQueries({ queryKey: ["my-balance"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось отправить заявку");
    } finally {
      setSubmitting(false);
    }
  }

  const tooShort = currentRangeDays !== null && currentRangeDays < minDays;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <h3>Новая заявка на отпуск</h3>

      {balance && (
        <p>
          Баланс {balance.year}: начислено {balance.accrued_days}, использовано{" "}
          {balance.used_days}, остаток <strong>{balance.remaining_days}</strong> дн.
          {(drafts?.length ?? 0) > 0 && remainingAfterPlanned !== null && (
            <>
              {" "}
              — выбрано в плане {plannedTotalDays} дн., не выбрано ещё{" "}
              <strong>{remainingAfterPlanned}</strong> дн.
            </>
          )}
        </p>
      )}

      <div style={{ display: "flex", gap: 16, alignItems: "flex-start", flexWrap: "wrap" }}>
        <div style={{ flex: "0 0 928px", maxWidth: 928 }}>
          <DateRangePicker
            range={range}
            onChange={setRange}
            blockedRanges={blockedRanges ?? []}
            plannedRanges={plannedRanges}
            year={planningYear}
          />
        </div>

        <div
          style={{
            flex: "0 0 260px",
            border: "1px solid #ddd",
            borderRadius: 6,
            padding: 12,
            display: "flex",
            flexDirection: "column",
            gap: 10,
            position: "sticky",
            top: 16,
          }}
        >
          <div>
            {currentRangeDays !== null ? (
              <p style={{ margin: 0, color: tooShort ? "crimson" : undefined }}>
                Длительность: <strong>{currentRangeDays} дн.</strong>
                {tooShort && ` — минимум ${minDays} дн.`}
              </p>
            ) : (
              <p style={{ margin: 0, color: "#888" }}>Выберите период на календаре слева.</p>
            )}
          </div>

          <label>
            Комментарий к периоду
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              style={{ display: "block", width: "100%" }}
              rows={3}
            />
          </label>

          {bonusProgramEnabled && (
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                color: qualifiesForBonus ? undefined : "#aaa",
              }}
            >
              <input
                type="checkbox"
                checked={bonusRequested}
                disabled={!qualifiesForBonus}
                onChange={(e) => setBonusRequested(e.target.checked)}
              />
              Запросить доплату к отпуску
              {!qualifiesForBonus && ` (доступно от ${bonusMinDays + 1} дн.)`}
            </label>
          )}

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button type="button" onClick={handleAddPeriod} disabled={!canAddPeriod || adding}>
              Добавить период в план
            </button>
            <button type="button" onClick={clearSelection} disabled={!range?.from && !comment}>
              Очистить выбор
            </button>
          </div>
        </div>
      </div>

      {draftsLoading && <p>Загрузка плана…</p>}

      {drafts && drafts.length > 0 && (
        <div>
          <h4>План отпуска на {planningYear} год</h4>
          <table style={{ borderCollapse: "collapse", width: "100%" }}>
            <tbody>
              {drafts.map((d) => (
                <tr key={d.id}>
                  <td>
                    {d.date_from} — {d.date_to} ({d.days} дн.)
                    {d.bonus_requested && " 🎁 доплата"}
                  </td>
                  <td>{d.comment}</td>
                  <td>
                    <button type="button" onClick={() => handleRemovePeriod(d.id)}>
                      Убрать
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!readyToSubmit && (
            <p style={{ color: "#888" }}>
              Отправить на согласование можно, только когда выбран весь доступный остаток —
              осталось выбрать ещё {remainingAfterPlanned} дн.
            </p>
          )}
          <button type="button" onClick={handleSubmitAll} disabled={submitting || !readyToSubmit}>
            Отправить план на согласование
          </button>
        </div>
      )}

      {error && <p style={{ color: "crimson" }}>{error}</p>}
      {success && <p style={{ color: "green" }}>Заявка отправлена на согласование.</p>}
    </div>
  );
}
