import { useQuery } from "@tanstack/react-query";
import { format, parseISO } from "date-fns";
import { ru } from "date-fns/locale/ru";
import { useState } from "react";
import { apiFetch } from "../api/client";
import { getOrgLoad } from "../api/orgLoad";
import type { LoadBand, OrgLoadDayOut, OrgUnitOut } from "../api/types";

function groupByMonth(days: OrgLoadDayOut[]): { label: string; days: OrgLoadDayOut[] }[] {
  const groups = new Map<string, OrgLoadDayOut[]>();
  for (const day of days) {
    const monthKey = day.date.slice(0, 7);
    if (!groups.has(monthKey)) groups.set(monthKey, []);
    groups.get(monthKey)!.push(day);
  }
  return Array.from(groups.entries()).map(([monthKey, monthDays]) => ({
    label: format(parseISO(`${monthKey}-01`), "LLLL yyyy", { locale: ru }),
    days: monthDays,
  }));
}

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

export function OrgLoadDashboardPage() {
  const { data: orgUnits } = useQuery({
    queryKey: ["org-units"],
    queryFn: () => apiFetch<OrgUnitOut[]>("/org-units"),
  });
  const [selectedUnitId, setSelectedUnitId] = useState<string>("");

  const unitId = selectedUnitId || orgUnits?.[0]?.id || "";

  const { data: load } = useQuery({
    queryKey: ["org-load", unitId],
    queryFn: () => getOrgLoad(unitId),
    enabled: !!unitId,
  });

  return (
    <div>
      <h3>Загруженность отдела</h3>
      <label>
        Подразделение:{" "}
        <select value={unitId} onChange={(e) => setSelectedUnitId(e.target.value)}>
          {orgUnits?.map((u) => (
            <option key={u.id} value={u.id}>
              {u.name} ({u.unit_kind})
            </option>
          ))}
        </select>
      </label>

      {load && (
        <>
          <p>
            Списочная численность (без льготников): <strong>{load.headcount}</strong>
          </p>
          {groupByMonth(load.days).map((month) => (
            <div key={month.label} style={{ marginTop: 12 }}>
              <div style={{ fontWeight: 600, marginBottom: 4, textTransform: "capitalize" }}>
                {month.label}
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 2 }}>
                {month.days.map((day) => (
                  <div
                    key={day.date}
                    title={`${day.date}: ${day.on_leave} из ${day.headcount} в отпуске (${Math.round(day.fraction * 100)}%)`}
                    style={{
                      width: 28,
                      height: 32,
                      background: bandColor[day.band],
                      color: "white",
                      fontSize: 10,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      borderRadius: 3,
                    }}
                  >
                    <span>{format(parseISO(day.date), "d", { locale: ru })}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
          <div style={{ display: "flex", gap: 16, marginTop: 12, fontSize: "0.85em" }}>
            {(["green", "yellow", "red"] as LoadBand[]).map((band) => (
              <span key={band} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <span
                  style={{
                    display: "inline-block",
                    width: 12,
                    height: 12,
                    background: bandColor[band],
                    borderRadius: 2,
                  }}
                />
                {bandLabel[band]}
              </span>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
