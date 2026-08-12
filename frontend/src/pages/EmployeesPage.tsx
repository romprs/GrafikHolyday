import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { getUserBalance, listUsersWithRoles, setEmployeeCode, setUserBalance } from "../api/admin";
import { getRestrictionSettings } from "../api/calendar";
import { ApiError } from "../api/client";

function EmployeeCodeEditor({ userId, employeeCode }: { userId: string; employeeCode: string | null }) {
  const queryClient = useQueryClient();
  const [value, setValue] = useState(employeeCode ?? "");
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    setError(null);
    try {
      await setEmployeeCode(userId, value.trim() || null);
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось сохранить");
    }
  }

  return (
    <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        style={{ width: 90 }}
      />
      <button onClick={handleSave} disabled={value.trim() === (employeeCode ?? "")}>
        Сохранить
      </button>
      {error && <span style={{ color: "crimson", fontSize: "0.85em" }}>{error}</span>}
    </div>
  );
}

function BalanceEditor({ userId, year }: { userId: string; year: number }) {
  const queryClient = useQueryClient();
  const { data: balance } = useQuery({
    queryKey: ["user-balance", userId, year],
    queryFn: () => getUserBalance(userId, year),
  });
  const [accrued, setAccrued] = useState<string>("");
  const [carriedOver, setCarriedOver] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const accruedValue = accrued === "" ? balance?.accrued_days ?? 0 : Number(accrued);
  const carriedOverValue = carriedOver === "" ? balance?.carried_over_days ?? 0 : Number(carriedOver);

  async function handleSave() {
    setError(null);
    try {
      await setUserBalance(userId, {
        year,
        accrued_days: accruedValue,
        carried_over_days: carriedOverValue,
      });
      queryClient.invalidateQueries({ queryKey: ["user-balance", userId, year] });
      setAccrued("");
      setCarriedOver("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось сохранить");
    }
  }

  if (!balance) return null;

  return (
    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
      <span>
        начислено{" "}
        <input
          type="number"
          min={0}
          style={{ width: 60 }}
          value={accrued === "" ? balance.accrued_days : accrued}
          onChange={(e) => setAccrued(e.target.value)}
        />
      </span>
      <span>
        перенесено{" "}
        <input
          type="number"
          min={0}
          style={{ width: 60 }}
          value={carriedOver === "" ? balance.carried_over_days : carriedOver}
          onChange={(e) => setCarriedOver(e.target.value)}
        />
      </span>
      <span>
        остаток: <strong>{balance.remaining_days}</strong>
      </span>
      <button onClick={handleSave}>Сохранить</button>
      {error && <span style={{ color: "crimson" }}>{error}</span>}
    </div>
  );
}

export function EmployeesPage() {
  const { data: users } = useQuery({ queryKey: ["admin-users"], queryFn: listUsersWithRoles });
  const { data: restrictionSettings } = useQuery({
    queryKey: ["restriction-settings"],
    queryFn: getRestrictionSettings,
  });
  const planningYearSetting = restrictionSettings?.find((s) => s.key === "planning_year");
  const year =
    typeof planningYearSetting?.params.year === "number"
      ? planningYearSetting.params.year
      : new Date().getFullYear();

  return (
    <div>
      <h3>Сотрудники — начисление дней отпуска ({year} год)</h3>
      <p style={{ color: "#888", fontSize: "0.9em" }}>
        Пока проставляется вручную; отделы и иерархия уже синхронизируются из внешней системы
        (см. app/integrations/org_directory.py), балансы отпуска — нет.
      </p>
      <table style={{ borderCollapse: "collapse", width: "100%" }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left" }}>Сотрудник</th>
            <th style={{ textAlign: "left" }}>Табельный номер</th>
            <th style={{ textAlign: "left" }}>Баланс на {year} год</th>
          </tr>
        </thead>
        <tbody>
          {users
            ?.filter((u) => u.role === "employee" || u.role === "manager")
            .map((u) => (
              <tr key={u.id}>
                <td>
                  {u.full_name} ({u.email})
                </td>
                <td>
                  <EmployeeCodeEditor userId={u.id} employeeCode={u.employee_code} />
                </td>
                <td>
                  <BalanceEditor userId={u.id} year={year} />
                </td>
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}
