import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { updateRestrictionSetting } from "../api/admin";
import { getRestrictionSettings } from "../api/calendar";
import type { RestrictionSettingsOut } from "../api/types";

const keyLabelRu: Record<string, string> = {
  min_leave_duration: "Минимальная длительность отпуска",
  blocked_period_enforcement: "Блокировка недоступных периодов",
  department_load_thresholds: "Пороги загруженности отдела",
  leave_balance_limit: "Запрет заявок сверх остатка баланса",
  own_overlap_check: "Запрет пересекающихся заявок сотрудника",
  planning_year: "Плановый год",
  vacation_bonus: "Выплата ЕСВ к отпуску",
  vacation_bonus_new_hire_restriction: "Выплата ЕСВ по стажу — новичкам (стаж < года)",
  vacation_bonus_veteran_restriction: "Выплата ЕСВ по стажу — стажистам (стаж ≥ года)",
};

function SettingRow({ setting }: { setting: RestrictionSettingsOut }) {
  const queryClient = useQueryClient();
  const [enabled, setEnabled] = useState(setting.enabled);
  const [params, setParams] = useState<Record<string, unknown>>(setting.params);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setEnabled(setting.enabled);
    setParams(setting.params);
  }, [setting]);

  async function handleSave() {
    setSaving(true);
    try {
      await updateRestrictionSetting(setting.key, { enabled, params });
      queryClient.invalidateQueries({ queryKey: ["restriction-settings"] });
    } finally {
      setSaving(false);
    }
  }

  const isPlanningYear = setting.key === "planning_year";
  // Без этого признака кнопка «Сохранить» выглядит одинаково всегда, и
  // после смены параметра не бросается в глаза, что её ещё нужно нажать.
  const dirty =
    enabled !== setting.enabled || JSON.stringify(params) !== JSON.stringify(setting.params);

  return (
    <tr>
      <td style={{ padding: "8px 0" }}>{keyLabelRu[setting.key] ?? setting.key}</td>
      <td>
        {!isPlanningYear && (
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
          />
        )}
      </td>
      <td>
        {isPlanningYear && (
          <label>
            год:{" "}
            <input
              type="number"
              min={2020}
              max={2100}
              style={{ width: 80 }}
              value={(params.year as number) ?? new Date().getFullYear()}
              onChange={(e) => setParams({ ...params, year: Number(e.target.value) })}
            />
          </label>
        )}
        {setting.key === "min_leave_duration" && (
          <label>
            мин. дней:{" "}
            <input
              type="number"
              min={1}
              style={{ width: 60 }}
              value={(params.min_days as number) ?? 1}
              onChange={(e) => setParams({ ...params, min_days: Number(e.target.value) })}
            />
          </label>
        )}
        {setting.key === "vacation_bonus" && (
          <label>
            более, дней:{" "}
            <input
              type="number"
              min={1}
              style={{ width: 60 }}
              value={(params.min_days as number) ?? 14}
              onChange={(e) => setParams({ ...params, min_days: Number(e.target.value) })}
            />
          </label>
        )}
        {setting.key === "vacation_bonus_new_hire_restriction" && (
          <>
            <label>
              мес. со дня приёма:{" "}
              <input
                type="number"
                min={1}
                style={{ width: 60 }}
                value={(params.months as number) ?? 10}
                onChange={(e) => setParams({ ...params, months: Number(e.target.value) })}
              />
            </label>
            <div className="hint" style={{ maxWidth: 340 }}>
              Для сотрудников со стажем менее года — ЕСВ доступна не раньше этого срока с даты
              приёма (User.hire_date). Без даты приёма ограничение не действует.
            </div>
          </>
        )}
        {setting.key === "vacation_bonus_veteran_restriction" && (
          <>
            <label>
              сдвиг, мес.:{" "}
              <input
                type="number"
                min={1}
                max={11}
                style={{ width: 60 }}
                value={(params.shift_months as number) ?? 6}
                onChange={(e) => setParams({ ...params, shift_months: Number(e.target.value) })}
              />
            </label>
            <div className="hint" style={{ maxWidth: 340 }}>
              Для сотрудников со стажем год и более — принятым в 1-й половине планового года
              ограничений нет; принятым во 2-й — доступно с (месяц приёма − сдвиг) того же
              планового года, ежегодно (например, приём в декабре при сдвиге 6 → доступно с июня
              каждого планового года). Без даты приёма ограничение не действует.
            </div>
          </>
        )}
        {setting.key === "department_load_thresholds" && (
          <>
            <label>
              жёлтый от, %:{" "}
              <input
                type="number"
                min={0}
                max={100}
                style={{ width: 60 }}
                value={Math.round(((params.yellow as number) ?? 0.3) * 100)}
                onChange={(e) =>
                  setParams({ ...params, yellow: Number(e.target.value) / 100 })
                }
              />
            </label>{" "}
            <label>
              красный от, %:{" "}
              <input
                type="number"
                min={0}
                max={100}
                style={{ width: 60 }}
                value={Math.round(((params.red as number) ?? 0.5) * 100)}
                onChange={(e) => setParams({ ...params, red: Number(e.target.value) / 100 })}
              />
            </label>
          </>
        )}
      </td>
      <td>
        <button
          className={dirty ? "btn-primary" : "btn-ghost"}
          onClick={handleSave}
          disabled={saving || !dirty}
        >
          {dirty ? "Сохранить*" : "Сохранено"}
        </button>
      </td>
    </tr>
  );
}

export function RestrictionSettingsPage() {
  const { data: settings } = useQuery({
    queryKey: ["restriction-settings"],
    queryFn: getRestrictionSettings,
  });

  return (
    <div>
      <h3>Управляемые ограничения</h3>
      <div className="panel">
      <table className="t">
        <thead>
          <tr>
            <th>Ограничение</th>
            <th>Вкл.</th>
            <th>Параметры</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {settings
            // У этих ключей своя полноценная форма на вкладке «Интеграции» —
            // здесь для них не было ни строкового наименования (ключ
            // показывался как есть, по-английски), ни редактируемых
            // параметров, только чекбокс "вкл", дублирующий и путающий с
            // формой на другой вкладке.
            ?.filter(
              (s) =>
                s.key !== "external_source_connection" &&
                s.key !== "auth_configuration" &&
                s.key !== "study_periods_source" &&
                s.key !== "vacation_days_source",
            )
            .map((s) => (
              <SettingRow key={s.key} setting={s} />
            ))}
        </tbody>
      </table>
      </div>
    </div>
  );
}
