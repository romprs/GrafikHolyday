import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  createUser,
  deleteUser,
  getUserBalance,
  listUsersWithRoles,
  setEmployeeCode,
  setUserBalance,
  updateUser,
} from "../api/admin";
import { getRestrictionSettings } from "../api/calendar";
import { apiFetch, ApiError } from "../api/client";
import type { OrgUnitOut, UserWithRoleOut } from "../api/types";

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

function EmployeeForm({
  orgUnits,
  initial,
  onSaved,
  onCancel,
}: {
  orgUnits: OrgUnitOut[];
  initial: UserWithRoleOut | null;
  onSaved: () => void;
  onCancel: () => void;
}) {
  const [email, setEmail] = useState(initial?.email ?? "");
  const [fullName, setFullName] = useState(initial?.full_name ?? "");
  const [orgUnitId, setOrgUnitId] = useState(initial?.org_unit_id ?? "");
  const [hasBenefits, setHasBenefits] = useState(initial?.has_benefits ?? false);
  const [isActive, setIsActive] = useState(initial?.is_active ?? true);
  const [employeeCode, setEmployeeCodeValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      if (initial) {
        await updateUser(initial.id, {
          email,
          full_name: fullName,
          org_unit_id: orgUnitId || null,
          has_benefits: hasBenefits,
          is_active: isActive,
        });
      } else {
        await createUser({
          email,
          full_name: fullName,
          org_unit_id: orgUnitId || null,
          has_benefits: hasBenefits,
          employee_code: employeeCode || null,
        });
      }
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось сохранить сотрудника");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        display: "flex",
        gap: 6,
        flexWrap: "wrap",
        alignItems: "center",
        margin: "6px 0",
        padding: 8,
        background: "#f7f7f7",
        borderRadius: 4,
      }}
    >
      <input
        value={fullName}
        onChange={(e) => setFullName(e.target.value)}
        placeholder="ФИО"
        required
        style={{ minWidth: 200 }}
      />
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="email"
        required
        style={{ minWidth: 200 }}
      />
      <select value={orgUnitId} onChange={(e) => setOrgUnitId(e.target.value)}>
        <option value="">— без подразделения —</option>
        {orgUnits.map((u) => (
          <option key={u.id} value={u.id}>
            {u.name}
          </option>
        ))}
      </select>
      {!initial && (
        <input
          value={employeeCode}
          onChange={(e) => setEmployeeCodeValue(e.target.value)}
          placeholder="Табельный номер"
          style={{ width: 130 }}
        />
      )}
      <label>
        <input type="checkbox" checked={hasBenefits} onChange={(e) => setHasBenefits(e.target.checked)} />{" "}
        льготы
      </label>
      {initial && (
        <label>
          <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />{" "}
          активен
        </label>
      )}
      <button type="submit" disabled={saving}>
        Сохранить
      </button>
      <button type="button" onClick={onCancel} disabled={saving}>
        Отмена
      </button>
      {error && <span style={{ color: "crimson" }}>{error}</span>}
    </form>
  );
}

export function EmployeesPage() {
  const queryClient = useQueryClient();
  const { data: users } = useQuery({ queryKey: ["admin-users"], queryFn: listUsersWithRoles });
  const { data: orgUnits } = useQuery({
    queryKey: ["org-units"],
    queryFn: () => apiFetch<OrgUnitOut[]>("/org-units"),
  });
  const { data: restrictionSettings } = useQuery({
    queryKey: ["restriction-settings"],
    queryFn: getRestrictionSettings,
  });
  const planningYearSetting = restrictionSettings?.find((s) => s.key === "planning_year");
  const year =
    typeof planningYearSetting?.params.year === "number"
      ? planningYearSetting.params.year
      : new Date().getFullYear();

  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  function refresh() {
    setCreating(false);
    setEditingId(null);
    queryClient.invalidateQueries({ queryKey: ["admin-users"] });
  }

  async function handleDeactivate(userId: string) {
    if (!confirm("Деактивировать сотрудника? Он больше не сможет войти в систему.")) return;
    try {
      await deleteUser(userId);
      refresh();
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Не удалось деактивировать сотрудника");
    }
  }

  return (
    <div>
      <h3>Сотрудники ({year} год)</h3>
      <p style={{ color: "#888", fontSize: "0.9em" }}>
        Отделы и иерархия уже синхронизируются из внешней системы (см.
        app/integrations/org_directory.py); сотрудников и балансы отпуска пока ведёте здесь вручную.
      </p>

      <div style={{ marginBottom: 8 }}>
        <button type="button" onClick={() => setCreating(true)} disabled={creating}>
          + добавить сотрудника
        </button>
      </div>
      {creating && (
        <EmployeeForm orgUnits={orgUnits ?? []} initial={null} onSaved={refresh} onCancel={() => setCreating(false)} />
      )}

      <table style={{ borderCollapse: "collapse", width: "100%" }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left" }}>Сотрудник</th>
            <th style={{ textAlign: "left" }}>Табельный номер</th>
            <th style={{ textAlign: "left" }}>Баланс на {year} год</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {users
            ?.filter((u) => u.role === "employee" || u.role === "manager")
            .map((u) =>
              editingId === u.id ? (
                <tr key={u.id}>
                  <td colSpan={4}>
                    <EmployeeForm orgUnits={orgUnits ?? []} initial={u} onSaved={refresh} onCancel={() => setEditingId(null)} />
                  </td>
                </tr>
              ) : (
                <tr key={u.id} style={{ opacity: u.is_active ? 1 : 0.5 }}>
                  <td>
                    {u.full_name} ({u.email})
                    {!u.is_active && " — деактивирован"}
                  </td>
                  <td>
                    <EmployeeCodeEditor userId={u.id} employeeCode={u.employee_code} />
                  </td>
                  <td>
                    <BalanceEditor userId={u.id} year={year} />
                  </td>
                  <td>
                    <button type="button" onClick={() => setEditingId(u.id)}>
                      изменить
                    </button>{" "}
                    {u.is_active && (
                      <button type="button" onClick={() => handleDeactivate(u.id)}>
                        деактивировать
                      </button>
                    )}
                  </td>
                </tr>
              ),
            )}
        </tbody>
      </table>
    </div>
  );
}
