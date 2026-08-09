import { useQuery } from "@tanstack/react-query";
import { getBlockedRanges, getRestrictionSettings, getTeamCalendar } from "../api/calendar";

const statusLabel: Record<string, string> = {
  pending_approval: "на согласовании",
  approved: "согласовано",
};

const statusColor: Record<string, string> = {
  pending_approval: "#fbc02d",
  approved: "#4caf50",
};

export function TeamCalendarPage() {
  const { data: restrictionSettings } = useQuery({
    queryKey: ["restriction-settings"],
    queryFn: getRestrictionSettings,
  });
  const planningYearSetting = restrictionSettings?.find((s) => s.key === "planning_year");
  const planningYear =
    typeof planningYearSetting?.params.year === "number"
      ? planningYearSetting.params.year
      : new Date().getFullYear();

  // Скоуп по плановому году, а не "сегодня + N дней" — иначе заявки на год,
  // выставленный вперёд относительно реальной текущей даты, не попадали бы
  // в окно и календарь выглядел бы пустым.
  const { data: teamLeave } = useQuery({
    queryKey: ["team-calendar", planningYear],
    queryFn: () => getTeamCalendar(`${planningYear}-01-01`, `${planningYear}-12-31`),
  });
  const { data: blockedRanges } = useQuery({
    queryKey: ["blocked-ranges", planningYear],
    queryFn: () => getBlockedRanges(`${planningYear}-01-01`, `${planningYear}-12-31`),
  });

  return (
    <div>
      <h3>Календарь отдела ({planningYear} год)</h3>

      <h4>Отпуска коллег (согласованные и на согласовании)</h4>
      <p style={{ color: "#888" }}>
        Заявки на согласовании тоже показаны — чтобы оценить пересечение с ними до принятия
        решения.
      </p>
      {teamLeave?.length === 0 && <p>Нет отпусков на {planningYear} год.</p>}
      <ul>
        {teamLeave?.map((t, i) => (
          <li key={i}>
            <span
              style={{
                display: "inline-block",
                width: 10,
                height: 10,
                borderRadius: "50%",
                background: statusColor[t.status] ?? "#999",
                marginRight: 6,
              }}
            />
            {t.date_from} — {t.date_to} ({statusLabel[t.status] ?? t.status})
          </li>
        ))}
      </ul>

      <h4>Недоступные периоды</h4>
      {blockedRanges?.length === 0 && <p>Недоступных периодов нет.</p>}
      <ul>
        {blockedRanges?.map((b, i) => (
          <li key={i}>
            {b.date_from} — {b.date_to}: {b.reason}
          </li>
        ))}
      </ul>
    </div>
  );
}
