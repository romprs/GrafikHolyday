import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { updateRestrictionSetting } from "../api/admin";
import { getRestrictionSettings } from "../api/calendar";
import type { RestrictionSettingsOut } from "../api/types";

const keyLabelRu: Record<string, string> = {
  min_leave_duration: "Минимальная длительность отпуска",
  blocked_period_enforcement: "Блокировка недоступных периодов",
  department_load_thresholds: "Пороги загруженности отдела",
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

  return (
    <tr>
      <td style={{ padding: "8px 0" }}>{keyLabelRu[setting.key] ?? setting.key}</td>
      <td>
        <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
      </td>
      <td>
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
        <button onClick={handleSave} disabled={saving}>
          Сохранить
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
      <table style={{ borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left" }}>Ограничение</th>
            <th>Вкл.</th>
            <th style={{ textAlign: "left" }}>Параметры</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {settings?.map((s) => (
            <SettingRow key={s.key} setting={s} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
