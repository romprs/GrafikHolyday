import { eachDayOfInterval, format, parseISO } from "date-fns";
import { useMemo } from "react";
import { ru } from "date-fns/locale/ru";
import { DayButton, DayPicker, type DateRange, type DayButtonProps, type Matcher } from "react-day-picker";
import "react-day-picker/style.css";
import "./DateRangePicker.css";
import { isNonWorkingDay } from "../holidays";
import type { BlockedRangeOut } from "../api/types";

interface Props {
  range: DateRange | undefined;
  onChange: (range: DateRange | undefined) => void;
  /** Реально недоступные периоды (учёба, блокировки HR) — показываются зачёркнутыми. */
  blockedRanges: BlockedRangeOut[];
  /** Уже добавленные в план периоды — подсвечиваются фоном (не путать с недоступными). */
  plannedRanges?: BlockedRangeOut[];
  /** Плановый год — пикер показывает январь–декабрь именно этого года,
   * а не 12 месяцев вперёд от сегодня (см. настройку "Плановый год"). */
  year: number;
  /** День под курсором — для предпросмотра диапазона до второго клика (см. onHoverDayChange). */
  hoverDay?: Date;
  onHoverDayChange?: (day: Date | undefined) => void;
}

function toDateRangeMatchers(ranges: BlockedRangeOut[]): Matcher[] {
  return ranges.map((b) => ({
    from: parseISO(b.date_from),
    to: parseISO(b.date_to),
  }));
}

// Причина недоступности видна раньше только на отдельной странице
// "Недоступные периоды" — сотрудник, который просто планирует отпуск, её
// не видел вовсе. Разворачиваем диапазоны в карту "день -> причина(ы)" для
// подсказки по наведению прямо на календаре (см. CustomDayButton ниже).
function reasonByDate(ranges: BlockedRangeOut[]): Map<string, string> {
  const map = new Map<string, string>();
  for (const r of ranges) {
    for (const day of eachDayOfInterval({ start: parseISO(r.date_from), end: parseISO(r.date_to) })) {
      const key = format(day, "yyyy-MM-dd");
      const existing = map.get(key);
      map.set(key, existing ? `${existing}; ${r.reason}` : r.reason);
    }
  }
  return map;
}

function makeDayButtonWithTooltip(reasonMap: Map<string, string>) {
  return function CustomDayButton(props: DayButtonProps) {
    const reason = reasonMap.get(format(props.day.date, "yyyy-MM-dd"));
    return <DayButton {...props} title={reason ?? props.title} />;
  };
}

export function DateRangePicker({
  range,
  onChange,
  blockedRanges,
  plannedRanges,
  year,
  hoverDay,
  onHoverDayChange,
}: Props) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const yearStart = new Date(year, 0, 1);
  const planned = plannedRanges ?? [];

  const disabled: Matcher[] = [
    { before: today },
    ...toDateRangeMatchers(blockedRanges),
    ...toDateRangeMatchers(planned),
  ];

  // Причина недоступного дня — приоритетнее, чем "уже в плане", если день
  // почему-то попадает в оба (не должно случаться в норме, но на всякий
  // случай явное важнее).
  const dayTitles = useMemo(() => {
    const map = reasonByDate(planned);
    for (const [k, v] of reasonByDate(blockedRanges)) map.set(k, v);
    return map;
  }, [blockedRanges, planned]);
  const CustomDayButton = useMemo(() => makeDayButtonWithTooltip(dayTitles), [dayTitles]);

  // Предпросмотр диапазона при наведении. Библиотека завершает диапазон уже
  // на первом клике (from === to, однодневный диапазон) — считаем выбор
  // "ещё не завершённым пользователем", пока наведённый день отличается от
  // единственного выбранного, и показываем, что получится при втором клике.
  const isStillPicking =
    range?.from && range?.to && range.from.getTime() === range.to.getTime();
  const previewRange: Matcher[] =
    isStillPicking && hoverDay && hoverDay.getTime() !== range!.from!.getTime()
      ? [
          {
            from: range!.from! < hoverDay ? range!.from! : hoverDay,
            to: range!.from! < hoverDay ? hoverDay : range!.from!,
          },
        ]
      : [];

  return (
    <div>
      <div className="year-grid-picker">
        <DayPicker
          // defaultMonth ниже — неконтролируемый проп react-day-picker,
          // учитывается только при монтировании. Без key={year} календарь,
          // однажды смонтированный до загрузки планового года с бэка,
          // "застревал" бы на запасном годе и не переключался на реальный
          // плановый год, когда настройки приходят чуть позже.
          key={year}
          mode="range"
          locale={ru}
          selected={range}
          onSelect={onChange}
          disabled={disabled}
          numberOfMonths={12}
          defaultMonth={yearStart}
          disableNavigation
          hideNavigation
          onDayMouseEnter={(day) => onHoverDayChange?.(day)}
          onDayMouseLeave={() => onHoverDayChange?.(undefined)}
          modifiers={{
            nonWorking: isNonWorkingDay,
            blocked: toDateRangeMatchers(blockedRanges),
            planned: toDateRangeMatchers(planned),
            preview: previewRange,
          }}
          modifiersClassNames={{
            nonWorking: "day-nonworking",
            blocked: "day-blocked",
            planned: "day-planned",
            preview: "day-preview",
          }}
          components={{ DayButton: CustomDayButton }}
        />
      </div>
      <p style={{ fontSize: "0.85em", color: "var(--ink-mute)" }}>
        Светло-красным — выходные и праздничные дни. Серым фоном — недоступные для отпуска дни
        {blockedRanges.length > 0 && " (наведите на день — всплывёт причина)"}.
        {planned.length > 0 && <> Голубым — дни, уже добавленные в план отпуска.</>}
      </p>
    </div>
  );
}
