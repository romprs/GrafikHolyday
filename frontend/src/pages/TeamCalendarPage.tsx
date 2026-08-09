import { useQuery } from "@tanstack/react-query";
import { getBlockedRanges, getTeamCalendar } from "../api/calendar";

const statusLabel: Record<string, string> = {
  pending_approval: "на согласовании",
  approved: "согласовано",
};

const statusColor: Record<string, string> = {
  pending_approval: "#fbc02d",
  approved: "#4caf50",
};

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

      <h4>Отпуска коллег (согласованные и на согласовании)</h4>
      <p style={{ color: "#888" }}>
        Заявки на согласовании тоже показаны — чтобы оценить пересечение с ними до принятия
        решения.
      </p>
      {teamLeave?.length === 0 && <p>Нет отпусков в ближайшие 90 дней.</p>}
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
