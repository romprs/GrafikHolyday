import { useQuery, useQueryClient } from "@tanstack/react-query";
import { differenceInCalendarDays, format } from "date-fns";
import { useEffect, useRef, useState } from "react";
import type { DateRange } from "react-day-picker";
import { ApiError } from "../api/client";
import { getBlockedRanges, getRestrictionSettings } from "../api/calendar";
import { listMyDelegationTargets } from "../api/delegations";
import {
  addDraft,
  getMyBalance,
  listDrafts,
  removeDraft,
  submitDrafts,
  updateDraftBonus,
} from "../api/leaveRequests";
import { DateRangePicker } from "../components/DateRangePicker";

function toIsoDate(d: Date): string {
  return format(d, "yyyy-MM-dd");
}

export function RequestFormPage() {
  const queryClient = useQueryClient();
  const [range, setRange] = useState<DateRange | undefined>();
  const [hoverDay, setHoverDay] = useState<Date | undefined>();
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [adding, setAdding] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [onBehalfOf, setOnBehalfOf] = useState<string | undefined>(undefined);
  const lastAutoAddedKey = useRef<string | null>(null);

  const { data: restrictionSettings } = useQuery({
    queryKey: ["restriction-settings"],
    queryFn: getRestrictionSettings,
  });
  // Делегаты (и руководители, которым делегировали) видят переключатель
  // "от чьего имени" — за сотрудника, который сам системой не пользуется.
  const { data: delegationTargets } = useQuery({
    queryKey: ["delegation-targets"],
    queryFn: listMyDelegationTargets,
  });
  const { data: balance } = useQuery({
    queryKey: ["my-balance", onBehalfOf],
    queryFn: () => getMyBalance(onBehalfOf),
  });

  const planningYearSetting = restrictionSettings?.find((s) => s.key === "planning_year");
  const planningYear =
    typeof planningYearSetting?.params.year === "number"
      ? planningYearSetting.params.year
      : new Date().getFullYear();

  // Ограничиваем недоступные периоды плановым годом — иначе показывались бы
  // вперемешку блокировки из всех лет, а не только те, что относятся к
  // текущему плановому году, который видно на календаре.
  const { data: blockedRanges } = useQuery({
    queryKey: ["blocked-ranges", planningYear, onBehalfOf],
    queryFn: () => getBlockedRanges(`${planningYear}-01-01`, `${planningYear}-12-31`, onBehalfOf),
  });

  const { data: drafts, isLoading: draftsLoading } = useQuery({
    queryKey: ["drafts", planningYear, onBehalfOf],
    queryFn: () => listDrafts(planningYear, onBehalfOf),
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

  // react-day-picker завершает диапазон уже на первом клике (from === to) —
  // пока наведённый день отличается от него, считаем выбор "ещё не
  // завершённым" и показываем предпросмотр по наведению мыши, не дожидаясь
  // второго клика.
  const isStillPicking = !!(range?.from && range?.to && range.from.getTime() === range.to.getTime());
  const isPreview = isStillPicking && !!hoverDay && hoverDay.getTime() !== range!.from!.getTime();
  const previewDays = isPreview
    ? differenceInCalendarDays(
        range!.from! < hoverDay! ? hoverDay! : range!.from!,
        range!.from! < hoverDay! ? range!.from! : hoverDay!,
      ) + 1
    : null;
  const currentRangeDays = isPreview
    ? previewDays
    : range?.from && range?.to
      ? differenceInCalendarDays(range.to, range.from) + 1
      : null;

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
    setHoverDay(undefined);
  }

  async function handleAddPeriod(from: Date, to: Date) {
    setError(null);
    setSuccess(false);
    setAdding(true);
    try {
      await addDraft({
        date_from: toIsoDate(from),
        date_to: toIsoDate(to),
        on_behalf_of: onBehalfOf,
      });
      clearSelection();
      queryClient.invalidateQueries({ queryKey: ["drafts"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось добавить период");
    } finally {
      setAdding(false);
    }
  }

  async function handleToggleBonus(id: string, next: boolean) {
    setError(null);
    try {
      await updateDraftBonus(id, next);
      queryClient.invalidateQueries({ queryKey: ["drafts"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось изменить доплату");
    }
  }

  // Период формируется прямо кликом мыши на календаре — как только выбор
  // завершён (заданы обе даты) и длительность проходит минимальный порог,
  // период добавляется в план автоматически, без отдельной кнопки.
  useEffect(() => {
    if (!range?.from || !range?.to) return;
    const key = `${range.from.getTime()}-${range.to.getTime()}`;
    if (lastAutoAddedKey.current === key) return;
    const days = differenceInCalendarDays(range.to, range.from) + 1;
    if (days < minDays) return;
    lastAutoAddedKey.current = key;
    void handleAddPeriod(range.from, range.to);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [range?.from, range?.to, minDays]);

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
      await submitDrafts(planningYear, onBehalfOf);
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

      {delegationTargets && delegationTargets.length > 0 && (
        <label>
          Действовать от имени:{" "}
          <select
            value={onBehalfOf ?? ""}
            onChange={(e) => setOnBehalfOf(e.target.value || undefined)}
          >
            <option value="">Себя</option>
            {delegationTargets.map((t) => (
              <option key={t.id} value={t.id}>
                {t.full_name} ({t.email})
              </option>
            ))}
          </select>
        </label>
      )}

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
            hoverDay={hoverDay}
            onHoverDayChange={setHoverDay}
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
                {isPreview ? "Выбирается: " : "Длительность: "}
                <strong>{currentRangeDays} дн.</strong>
                {tooShort && ` — минимум ${minDays} дн.`}
                {isPreview && !tooShort && " (кликните ещё раз, чтобы завершить выбор)"}
              </p>
            ) : (
              <p style={{ margin: 0, color: "#888" }}>
                Выберите период на календаре: клик — начало, клик — конец. Период добавится в
                план автоматически.
              </p>
            )}
          </div>

          <div>
            <button type="button" onClick={clearSelection} disabled={!range?.from || adding}>
              Очистить выбор
            </button>
          </div>

          {draftsLoading && <p>Загрузка плана…</p>}

          {drafts && drafts.length > 0 && (
            <div>
              <h4 style={{ marginBottom: 4 }}>План отпуска на {planningYear} год</h4>
              <table style={{ borderCollapse: "collapse", width: "100%", fontSize: "0.9em" }}>
                <tbody>
                  {drafts.map((d) => (
                    <tr key={d.id}>
                      <td>
                        <div>
                          {d.date_from} — {d.date_to} ({d.days} дн.)
                        </div>
                        {bonusProgramEnabled && d.days > bonusMinDays && (
                          <label style={{ fontSize: "0.85em", color: "#888" }}>
                            <input
                              type="checkbox"
                              checked={d.bonus_requested}
                              onChange={(e) => handleToggleBonus(d.id, e.target.checked)}
                            />{" "}
                            🎁 доплата к этому периоду
                          </label>
                        )}
                      </td>
                      <td style={{ verticalAlign: "top" }}>
                        <button type="button" onClick={() => handleRemovePeriod(d.id)}>
                          Убрать
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!readyToSubmit && (
                <p style={{ color: "#888", fontSize: "0.85em" }}>
                  Отправить на согласование можно, только когда выбран весь доступный остаток —
                  осталось выбрать ещё {remainingAfterPlanned} дн.
                </p>
              )}
              <button
                type="button"
                onClick={handleSubmitAll}
                disabled={submitting || !readyToSubmit}
              >
                Отправить план на согласование
              </button>
            </div>
          )}

          {error && <p style={{ color: "crimson" }}>{error}</p>}
          {success && <p style={{ color: "green" }}>Заявка отправлена на согласование.</p>}
        </div>
      </div>
    </div>
  );
}
