import { useQuery } from "@tanstack/react-query";
import { getBlockedRanges, getTeamCalendar } from "../api/calendar";

export function TeamCalendarPage() {
  const { data: teamLeave } = useQuery({
    queryKey: ["team-calendar"],
    queryFn: getTeamCalendar,
  });
  const { data: blockedRanges } = useQuery({
    queryKey: ["blocked-ranges"],
    queryFn: getBlockedRanges,
  });

  return (
    <div>
      <h3>Календарь отдела</h3>

      <h4>Согласованные отпуска коллег</h4>
      {teamLeave?.length === 0 && <p>Нет согласованных отпусков в ближайшие 90 дней.</p>}
      <ul>
        {teamLeave?.map((t, i) => (
          <li key={i}>
            {t.date_from} — {t.date_to}
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
