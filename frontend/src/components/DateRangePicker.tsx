import { differenceInCalendarDays, parseISO } from "date-fns";
import { ru } from "date-fns/locale/ru";
import { DayPicker, type DateRange, type Matcher } from "react-day-picker";
import "react-day-picker/style.css";
import "./DateRangePicker.css";
import type { BlockedRangeOut } from "../api/types";

interface Props {
  range: DateRange | undefined;
  onChange: (range: DateRange | undefined) => void;
  blockedRanges: BlockedRangeOut[];
  minDays: number;
  /** Плановый год — пикер показывает январь–декабрь именно этого года,
   * а не 12 месяцев вперёд от сегодня (см. настройку "Плановый год"). */
  year: number;
}

function toDateRangeMatchers(blockedRanges: BlockedRangeOut[]): Matcher[] {
  return blockedRanges.map((b) => ({
    from: parseISO(b.date_from),
    to: parseISO(b.date_to),
  }));
}

export function DateRangePicker({ range, onChange, blockedRanges, minDays, year }: Props) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const yearStart = new Date(year, 0, 1);

  const disabled: Matcher[] = [{ before: today }, ...toDateRangeMatchers(blockedRanges)];

  const days =
    range?.from && range?.to ? differenceInCalendarDays(range.to, range.from) + 1 : null;
  const tooShort = days !== null && days < minDays;

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
          modifiers={{ blocked: toDateRangeMatchers(blockedRanges) }}
          modifiersStyles={{ blocked: { textDecoration: "line-through", color: "#b00" } }}
        />
      </div>
      {days !== null && (
        <p style={{ color: tooShort ? "crimson" : undefined }}>
          Длительность: {days} дн.
          {tooShort && ` — минимум ${minDays} дн.`}
        </p>
      )}
      {blockedRanges.length > 0 && (
        <p style={{ fontSize: "0.85em", color: "#888" }}>
          Зачёркнуты недоступные для отпуска дни (наведите — см. список ниже).
        </p>
      )}
    </div>
  );
}
