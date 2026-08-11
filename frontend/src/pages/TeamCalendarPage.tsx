import { useQuery } from "@tanstack/react-query";
import { format } from "date-fns";
import { ru } from "date-fns/locale/ru";
import { useAuth } from "../auth/AuthContext";
import { getBlockedRanges, getRestrictionSettings } from "../api/calendar";
import { getOrgLoad } from "../api/orgLoad";
import type { LoadBand } from "../api/types";

const bandColor: Record<LoadBand, string> = {
  green: "#4caf50",
  yellow: "#fbc02d",
  red: "#e53935",
};

const bandLabel: Record<LoadBand, string> = {
  green: "до 30%",
  yellow: "30–50%",
  red: "более 50%",
};

const MONTH_NAMES = Array.from({ length: 12 }, (_, i) =>
  format(new Date(2000, i, 1), "LLLL", { locale: ru }),
);

function daysInMonth(year: number, monthIndex: number): number {
  return new Date(year, monthIndex + 1, 0).getDate();
}

export function TeamCalendarPage() {
  const { currentUser } = useAuth();
  const { data: restrictionSettings } = useQuery({
    queryKey: ["restriction-settings"],
    queryFn: getRestrictionSettings,
  });
  const planningYearSetting = restrictionSettings?.find((s) => s.key === "planning_year");
  const planningYear =
    typeof planningYearSetting?.params.year === "number"
      ? planningYearSetting.params.year
      : new Date().getFullYear();

  const orgUnitId = currentUser?.org_unit_id ?? null;

  // Загруженность отдела — агрегат без имён (в отличие от детализации,
  // доступной руководителю), поэтому рядовому сотруднику виден только
  // сам факт "сколько коллег в отпуске", а не кто именно.
  const { data: load } = useQuery({
    queryKey: ["team-load", orgUnitId],
    queryFn: () => getOrgLoad(orgUnitId!),
    enabled: !!orgUnitId,
  });

  const { data: blockedRanges } = useQuery({
    queryKey: ["blocked-ranges", planningYear],
    queryFn: () => getBlockedRanges(`${planningYear}-01-01`, `${planningYear}-12-31`),
  });

  const daysByIso = new Map((load?.days ?? []).map((d) => [d.date, d]));

  return (
    <div>
      <h3>Загруженность отдела ({planningYear} год)</h3>

      {!orgUnitId && <p style={{ color: "#888" }}>Вы не привязаны к подразделению.</p>}

      {orgUnitId && (
        <>
          <div style={{ overflowX: "auto" }}>
            <table style={{ borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  <th />
                  {Array.from({ length: 31 }, (_, i) => (
                    <th key={i} style={{ width: 26, fontWeight: 400, fontSize: "0.8em" }}>
                      {i + 1}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {MONTH_NAMES.map((monthName, monthIndex) => {
                  const numDays = daysInMonth(planningYear, monthIndex);
                  return (
                    <tr key={monthName}>
                      <td
                        style={{
                          textAlign: "left",
                          padding: "2px 10px 2px 0",
                          whiteSpace: "nowrap",
                          textTransform: "capitalize",
                          fontWeight: 600,
                          fontSize: "0.9em",
                        }}
                      >
                        {monthName}
                      </td>
                      {Array.from({ length: 31 }, (_, i) => {
                        const day = i + 1;
                        if (day > numDays) return <td key={day} />;
                        const dateIso = format(new Date(planningYear, monthIndex, day), "yyyy-MM-dd");
                        const info = daysByIso.get(dateIso);
                        const empty = !info || info.on_leave === 0;
                        return (
                          <td key={day} style={{ padding: 1 }}>
                            <div
                              title={info ? `${dateIso}: ${info.on_leave}/${info.headcount} в отпуске` : undefined}
                              style={{
                                width: 22,
                                height: 22,
                                borderRadius: 3,
                                background: empty ? "#f0f0f0" : bandColor[info!.band],
                                color: empty ? "#bbb" : "white",
                                fontSize: 11,
                                fontWeight: 600,
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                              }}
                            >
                              {empty ? "" : info!.on_leave}
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div style={{ display: "flex", gap: 16, marginTop: 12, fontSize: "0.85em" }}>
            {(["green", "yellow", "red"] as LoadBand[]).map((b) => (
              <span key={b} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <span
                  style={{ width: 12, height: 12, borderRadius: 3, background: bandColor[b], display: "inline-block" }}
                />
                {bandLabel[b]}
              </span>
            ))}
          </div>
        </>
      )}

      <h4 style={{ marginTop: 24 }}>Недоступные периоды</h4>
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
