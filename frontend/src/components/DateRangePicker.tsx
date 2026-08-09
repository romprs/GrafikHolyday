import { parseISO } from "date-fns";
import { ru } from "date-fns/locale/ru";
import { DayPicker, type DateRange, type Matcher } from "react-day-picker";
import "react-day-picker/style.css";
import "./DateRangePicker.css";
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
}

function toDateRangeMatchers(ranges: BlockedRangeOut[]): Matcher[] {
  return ranges.map((b) => ({
    from: parseISO(b.date_from),
    to: parseISO(b.date_to),
  }));
}

export function DateRangePicker({ range, onChange, blockedRanges, plannedRanges, year }: Props) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const yearStart = new Date(year, 0, 1);
  const planned = plannedRanges ?? [];

  const disabled: Matcher[] = [
    { before: today },
    ...toDateRangeMatchers(blockedRanges),
    ...toDateRangeMatchers(planned),
  ];

  return (
    <div>
      <div className="year-grid-picker">
        <DayPicker
          mode="range"
          locale={ru}
          selected={range}
          onSelect={onChange}
          disabled={disabled}
          numberOfMonths={12}
          defaultMonth={yearStart}
          disableNavigation
          modifiers={{
            blocked: toDateRangeMatchers(blockedRanges),
            planned: toDateRangeMatchers(planned),
          }}
          modifiersStyles={{
            blocked: { textDecoration: "line-through", color: "#b00" },
            planned: { backgroundColor: "#cfe8ff", color: "#0a4a8f", fontWeight: 600 },
          }}
        />
      </div>
      {(blockedRanges.length > 0 || planned.length > 0) && (
        <p style={{ fontSize: "0.85em", color: "#888" }}>
          {blockedRanges.length > 0 && (
            <>
              Зачёркнуты недоступные для отпуска дни (наведите — см. список ниже).{" "}
            </>
          )}
          {planned.length > 0 && <>Подсвечены дни, уже добавленные в план отпуска.</>}
        </p>
      )}
    </div>
  );
}
