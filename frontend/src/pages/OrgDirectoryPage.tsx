import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  createOrgUnit,
  createUser,
  deleteOrgUnit,
  deleteUser,
  getUserBalance,
  grantRole,
  listUsersWithRoles,
  revokeRole,
  setEmployeeCode,
  setUserBalance,
  updateOrgUnit,
  updateUser,
} from "../api/admin";
import { getRestrictionSettings } from "../api/calendar";
import { apiFetch, ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { EmployeeRole, OrgUnitEmployeeOut, OrgUnitOut } from "../api/types";
import { roleLabel } from "./DevLoginPage";

// Единая форма отображения сотрудника — независимо от того, откуда данные
// пришли: полный набор полей от /admin/users (только hr_admin) или
// облегчённый /org-units/employees (доступен и руководителю, read-only).
interface DisplayEmployee {
  id: string;
  full_name: string;
  email: string;
  org_unit_id: string | null;
  role: EmployeeRole;
  has_benefits?: boolean;
  is_active?: boolean;
  employee_code?: string | null;
}

interface TreeNode {
  unit: OrgUnitOut;
  children: TreeNode[];
}

function buildTree(units: OrgUnitOut[]): TreeNode[] {
  const nodes = new Map<string, TreeNode>(units.map((u) => [u.id, { unit: u, children: [] }]));
  const roots: TreeNode[] = [];
  for (const unit of units) {
    const node = nodes.get(unit.id)!;
    const parent = unit.parent_id ? nodes.get(unit.parent_id) : undefined;
    if (parent) parent.children.push(node);
    else roots.push(node);
  }
  return roots;
}

function descendantIds(unitId: string, orgUnits: OrgUnitOut[]): Set<string> {
  const byParent = new Map<string, string[]>();
  for (const u of orgUnits) {
    if (!u.parent_id) continue;
    const list = byParent.get(u.parent_id) ?? [];
    list.push(u.id);
    byParent.set(u.parent_id, list);
  }
  const result = new Set<string>([unitId]);
  const stack = [unitId];
  while (stack.length) {
    const current = stack.pop()!;
    for (const child of byParent.get(current) ?? []) {
      if (!result.has(child)) {
        result.add(child);
        stack.push(child);
      }
    }
  }
  return result;
}

function matchesFilters(
  e: DisplayEmployee,
  nameFilter: string,
  roleFilter: string,
  unitFilterIds: Set<string> | null,
): boolean {
  if (nameFilter && !e.full_name.toLowerCase().includes(nameFilter.toLowerCase())) return false;
  if (roleFilter && e.role !== roleFilter) return false;
  if (unitFilterIds && (!e.org_unit_id || !unitFilterIds.has(e.org_unit_id))) return false;
  return true;
}

type UnitEditState = { mode: "create"; parentId: string | null } | { mode: "edit"; unit: OrgUnitOut };

function OrgUnitForm({
  orgUnits,
  employees,
  state,
  onSaved,
  onCancel,
}: {
  orgUnits: OrgUnitOut[];
  employees: DisplayEmployee[];
  state: UnitEditState;
  onSaved: () => void;
  onCancel: () => void;
}) {
  const initial = state.mode === "edit" ? state.unit : null;
  const [name, setName] = useState(initial?.name ?? "");
  const [unitKind, setUnitKind] = useState(initial?.unit_kind ?? "");
  const [parentId, setParentId] = useState(
    initial?.parent_id ?? (state.mode === "create" ? state.parentId ?? "" : ""),
  );
  const [headId, setHeadId] = useState(initial?.head_user_id ?? "");
  const [isActive, setIsActive] = useState(initial?.is_active ?? true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      const payload = {
        name,
        unit_kind: unitKind || null,
        parent_id: parentId || null,
        head_user_id: headId || null,
      };
      if (state.mode === "create") {
        await createOrgUnit(payload);
      } else {
        await updateOrgUnit(state.unit.id, { ...payload, is_active: isActive });
      }
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось сохранить подразделение");
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
        background: "#f0f4ff",
        borderRadius: 4,
      }}
    >
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Название"
        required
        style={{ minWidth: 200 }}
      />
      <input
        value={unitKind ?? ""}
        onChange={(e) => setUnitKind(e.target.value)}
        placeholder="Тип (отдел, управление…)"
        style={{ width: 160 }}
      />
      <select value={parentId} onChange={(e) => setParentId(e.target.value)}>
        <option value="">— без родителя —</option>
        {orgUnits
          .filter((u) => state.mode !== "edit" || u.id !== state.unit.id)
          .map((u) => (
            <option key={u.id} value={u.id}>
              {u.name}
            </option>
          ))}
      </select>
      <select value={headId} onChange={(e) => setHeadId(e.target.value)}>
        <option value="">— без руководителя —</option>
        {employees.map((emp) => (
          <option key={emp.id} value={emp.id}>
            {emp.full_name}
          </option>
        ))}
      </select>
      {state.mode === "edit" && (
        <label>
          <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />{" "}
          активно
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

function EmployeeForm({
  orgUnits,
  initial,
  defaultOrgUnitId,
  onSaved,
  onCancel,
}: {
  orgUnits: OrgUnitOut[];
  initial: DisplayEmployee | null;
  defaultOrgUnitId: string | null;
  onSaved: () => void;
  onCancel: () => void;
}) {
  const [email, setEmail] = useState(initial?.email ?? "");
  const [fullName, setFullName] = useState(initial?.full_name ?? "");
  const [orgUnitId, setOrgUnitId] = useState(initial?.org_unit_id ?? defaultOrgUnitId ?? "");
  const [hasBenefits, setHasBenefits] = useState(initial?.has_benefits ?? false);
  const [isActive, setIsActive] = useState(initial?.is_active ?? true);
  const [employeeCode, setEmployeeCodeValue] = useState(initial?.employee_code ?? "");
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
        if (employeeCode.trim() !== (initial.employee_code ?? "")) {
          await setEmployeeCode(initial.id, employeeCode.trim() || null);
        }
      } else {
        await createUser({
          email,
          full_name: fullName,
          org_unit_id: orgUnitId || null,
          has_benefits: hasBenefits,
          employee_code: employeeCode.trim() || null,
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
        margin: "4px 0",
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
      <input
        value={employeeCode}
        onChange={(e) => setEmployeeCodeValue(e.target.value)}
        placeholder="Табельный номер"
        style={{ width: 130 }}
      />
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

function BalanceInline({ userId, year }: { userId: string; year: number }) {
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
      await setUserBalance(userId, { year, accrued_days: accruedValue, carried_over_days: carriedOverValue });
      queryClient.invalidateQueries({ queryKey: ["user-balance", userId, year] });
      setAccrued("");
      setCarriedOver("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось сохранить");
    }
  }

  if (!balance) return null;

  return (
    <span style={{ display: "inline-flex", gap: 6, alignItems: "center", fontSize: "0.85em" }}>
      начислено{" "}
      <input
        type="number"
        min={0}
        style={{ width: 50 }}
        value={accrued === "" ? balance.accrued_days : accrued}
        onChange={(e) => setAccrued(e.target.value)}
      />
      перенесено{" "}
      <input
        type="number"
        min={0}
        style={{ width: 50 }}
        value={carriedOver === "" ? balance.carried_over_days : carriedOver}
        onChange={(e) => setCarriedOver(e.target.value)}
      />
      остаток: <strong>{balance.remaining_days}</strong>
      <button onClick={handleSave}>Сохранить</button>
      {error && <span style={{ color: "crimson" }}>{error}</span>}
    </span>
  );
}

function EmployeeRow({
  employee,
  orgUnits,
  isHrAdmin,
  currentUserId,
  year,
  editing,
  setEditing,
  onSaved,
}: {
  employee: DisplayEmployee;
  orgUnits: OrgUnitOut[];
  isHrAdmin: boolean;
  currentUserId: string | undefined;
  year: number;
  editing: boolean;
  setEditing: (id: string | null) => void;
  onSaved: () => void;
}) {
  const queryClient = useQueryClient();

  async function handleDeactivate() {
    if (!confirm("Деактивировать сотрудника? Он больше не сможет войти в систему.")) return;
    try {
      await deleteUser(employee.id);
      onSaved();
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Не удалось деактивировать сотрудника");
    }
  }

  async function handleRoleToggle() {
    try {
      if (employee.role === "hr_admin") {
        await revokeRole(employee.id, "hr_admin");
      } else {
        await grantRole(employee.id, "hr_admin");
      }
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Не удалось изменить роль");
    }
  }

  if (editing) {
    return (
      <li>
        <EmployeeForm
          orgUnits={orgUnits}
          initial={employee}
          defaultOrgUnitId={employee.org_unit_id}
          onSaved={() => {
            setEditing(null);
            onSaved();
          }}
          onCancel={() => setEditing(null)}
        />
      </li>
    );
  }

  return (
    <li
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: 8,
        alignItems: "center",
        padding: "2px 0",
        opacity: employee.is_active === false ? 0.5 : 1,
        color: employee.role === "employee" ? "inherit" : "#2e7d32",
      }}
    >
      <span>
        {employee.full_name} ({employee.email})
        {employee.role !== "employee" && ` — ${roleLabel(employee.role)}`}
        {employee.has_benefits && " — льготник"}
        {employee.employee_code && ` — таб. № ${employee.employee_code}`}
        {employee.is_active === false && " — деактивирован"}
      </span>
      {isHrAdmin && (
        <span style={{ display: "flex", gap: 6, fontSize: "0.85em" }}>
          <BalanceInline userId={employee.id} year={year} />
          <button type="button" onClick={() => setEditing(employee.id)}>
            изменить
          </button>
          <button type="button" onClick={handleRoleToggle} disabled={employee.id === currentUserId}>
            {employee.role === "hr_admin" ? "забрать HR-admin" : "выдать HR-admin"}
          </button>
          {employee.is_active !== false && (
            <button type="button" onClick={handleDeactivate}>
              деактивировать
            </button>
          )}
        </span>
      )}
    </li>
  );
}

function OrgUnitNode({
  node,
  depth,
  employeesByUnit,
  visibleEmployeeIds,
  forceExpanded,
  expanded,
  toggleExpanded,
  orgUnits,
  allEmployees,
  isHrAdmin,
  currentUserId,
  year,
  unitEditState,
  setUnitEditState,
  editingEmployeeId,
  setEditingEmployeeId,
  creatingEmployeeUnitId,
  setCreatingEmployeeUnitId,
  onSaved,
  filtersActive,
}: {
  node: TreeNode;
  depth: number;
  employeesByUnit: Map<string, DisplayEmployee[]>;
  visibleEmployeeIds: Set<string> | null;
  forceExpanded: Set<string>;
  expanded: Set<string>;
  toggleExpanded: (id: string) => void;
  orgUnits: OrgUnitOut[];
  allEmployees: DisplayEmployee[];
  isHrAdmin: boolean;
  currentUserId: string | undefined;
  year: number;
  unitEditState: UnitEditState | null;
  setUnitEditState: (s: UnitEditState | null) => void;
  editingEmployeeId: string | null;
  setEditingEmployeeId: (id: string | null) => void;
  creatingEmployeeUnitId: string | null | undefined;
  setCreatingEmployeeUnitId: (id: string | null | undefined) => void;
  onSaved: () => void;
  filtersActive: boolean;
}) {
  const isOpen = filtersActive ? forceExpanded.has(node.unit.id) : expanded.has(node.unit.id);
  const employeesHere = (employeesByUnit.get(node.unit.id) ?? []).filter(
    (e) => !visibleEmployeeIds || visibleEmployeeIds.has(e.id),
  );
  const head = allEmployees.find((e) => e.id === node.unit.head_user_id);
  const isEditingThis = unitEditState?.mode === "edit" && unitEditState.unit.id === node.unit.id;
  const isAddingChildHere = unitEditState?.mode === "create" && unitEditState.parentId === node.unit.id;
  const isAddingEmployeeHere = creatingEmployeeUnitId === node.unit.id;

  // При активных фильтрах прячем подразделения, в которых (и во всех
  // дочерних) нет ни одного подходящего сотрудника — иначе дерево из 270
  // подразделений реального источника было бы бесполезно листать вручную.
  if (filtersActive && !forceExpanded.has(node.unit.id)) return null;

  async function handleDeleteUnit() {
    if (!confirm(`Деактивировать подразделение «${node.unit.name}»?`)) return;
    try {
      await deleteOrgUnit(node.unit.id);
      onSaved();
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Не удалось деактивировать подразделение");
    }
  }

  return (
    <div style={{ marginLeft: depth === 0 ? 0 : 20, marginTop: 6 }}>
      <div style={{ fontWeight: 600, display: "flex", alignItems: "center", gap: 6 }}>
        <button
          type="button"
          onClick={() => toggleExpanded(node.unit.id)}
          style={{
            border: "none",
            background: "none",
            cursor: "pointer",
            width: 18,
            fontWeight: 700,
            padding: 0,
          }}
          title={isOpen ? "Свернуть" : "Развернуть"}
        >
          {isOpen ? "▾" : "▸"}
        </button>
        <span>
          {node.unit.name}
          {node.unit.unit_kind && <span style={{ fontWeight: 400, color: "#888" }}> ({node.unit.unit_kind})</span>}
          {head && <span style={{ fontWeight: 400, color: "#888" }}> — рук. {head.full_name}</span>}
          <span style={{ fontWeight: 400, color: "#aaa" }}> [{employeesHere.length}]</span>
        </span>
        {isHrAdmin && (
          <span style={{ fontWeight: 400, fontSize: "0.85em" }}>
            <button type="button" onClick={() => setUnitEditState({ mode: "edit", unit: node.unit })}>
              изменить
            </button>{" "}
            <button type="button" onClick={() => setUnitEditState({ mode: "create", parentId: node.unit.id })}>
              + подраздел
            </button>{" "}
            <button type="button" onClick={() => setCreatingEmployeeUnitId(node.unit.id)}>
              + сотрудник
            </button>{" "}
            <button type="button" onClick={handleDeleteUnit}>
              деактивировать
            </button>
          </span>
        )}
      </div>

      {isOpen && (
        <>
          {isEditingThis && (
            <OrgUnitForm
              orgUnits={orgUnits}
              employees={allEmployees}
              state={unitEditState}
              onSaved={() => {
                setUnitEditState(null);
                onSaved();
              }}
              onCancel={() => setUnitEditState(null)}
            />
          )}
          {isAddingChildHere && (
            <OrgUnitForm
              orgUnits={orgUnits}
              employees={allEmployees}
              state={unitEditState}
              onSaved={() => {
                setUnitEditState(null);
                onSaved();
              }}
              onCancel={() => setUnitEditState(null)}
            />
          )}
          {isAddingEmployeeHere && (
            <EmployeeForm
              orgUnits={orgUnits}
              initial={null}
              defaultOrgUnitId={node.unit.id}
              onSaved={() => {
                setCreatingEmployeeUnitId(undefined);
                onSaved();
              }}
              onCancel={() => setCreatingEmployeeUnitId(undefined)}
            />
          )}

          {employeesHere.length > 0 && (
            <ul style={{ margin: "2px 0 2px 26px", padding: 0, listStyle: "none" }}>
              {employeesHere.map((e) => (
                <EmployeeRow
                  key={e.id}
                  employee={e}
                  orgUnits={orgUnits}
                  isHrAdmin={isHrAdmin}
                  currentUserId={currentUserId}
                  year={year}
                  editing={editingEmployeeId === e.id}
                  setEditing={setEditingEmployeeId}
                  onSaved={onSaved}
                />
              ))}
            </ul>
          )}

          {node.children.map((child) => (
            <OrgUnitNode
              key={child.unit.id}
              node={child}
              depth={depth + 1}
              employeesByUnit={employeesByUnit}
              visibleEmployeeIds={visibleEmployeeIds}
              forceExpanded={forceExpanded}
              expanded={expanded}
              toggleExpanded={toggleExpanded}
              orgUnits={orgUnits}
              allEmployees={allEmployees}
              isHrAdmin={isHrAdmin}
              currentUserId={currentUserId}
              year={year}
              unitEditState={unitEditState}
              setUnitEditState={setUnitEditState}
              editingEmployeeId={editingEmployeeId}
              setEditingEmployeeId={setEditingEmployeeId}
              creatingEmployeeUnitId={creatingEmployeeUnitId}
              setCreatingEmployeeUnitId={setCreatingEmployeeUnitId}
              onSaved={onSaved}
              filtersActive={filtersActive}
            />
          ))}
        </>
      )}
    </div>
  );
}

export function OrgDirectoryPage() {
  const { currentUser } = useAuth();
  const isHrAdmin = currentUser?.role === "hr_admin";
  const queryClient = useQueryClient();

  const { data: orgUnits } = useQuery({
    queryKey: ["org-units"],
    queryFn: () => apiFetch<OrgUnitOut[]>("/org-units"),
  });
  const { data: adminUsers } = useQuery({
    queryKey: ["admin-users"],
    queryFn: listUsersWithRoles,
    enabled: isHrAdmin,
  });
  const { data: basicEmployees } = useQuery({
    queryKey: ["org-unit-employees"],
    queryFn: () => apiFetch<OrgUnitEmployeeOut[]>("/org-units/employees"),
    enabled: !isHrAdmin,
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

  const employees: DisplayEmployee[] = useMemo(() => {
    if (isHrAdmin) return adminUsers ?? [];
    return (basicEmployees ?? []).map((e) => ({
      id: e.id,
      full_name: e.full_name,
      email: e.email,
      org_unit_id: e.org_unit_id,
      role: e.role,
    }));
  }, [isHrAdmin, adminUsers, basicEmployees]);

  const [unitEditState, setUnitEditState] = useState<UnitEditState | null>(null);
  const [editingEmployeeId, setEditingEmployeeId] = useState<string | null>(null);
  const [creatingEmployeeUnitId, setCreatingEmployeeUnitId] = useState<string | null | undefined>(undefined);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const [nameFilter, setNameFilter] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [unitFilter, setUnitFilter] = useState("");

  function refresh() {
    setUnitEditState(null);
    setEditingEmployeeId(null);
    setCreatingEmployeeUnitId(undefined);
    queryClient.invalidateQueries({ queryKey: ["org-units"] });
    queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    queryClient.invalidateQueries({ queryKey: ["org-unit-employees"] });
  }

  const tree = useMemo(() => buildTree(orgUnits ?? []), [orgUnits]);
  const employeesByUnit = useMemo(() => {
    const map = new Map<string, DisplayEmployee[]>();
    for (const e of employees) {
      if (!e.org_unit_id) continue;
      const list = map.get(e.org_unit_id) ?? [];
      list.push(e);
      map.set(e.org_unit_id, list);
    }
    for (const list of map.values()) list.sort((a, b) => a.full_name.localeCompare(b.full_name));
    return map;
  }, [employees]);
  const unassigned = employees.filter((e) => !e.org_unit_id);

  const unitFilterIds = useMemo(
    () => (unitFilter && orgUnits ? descendantIds(unitFilter, orgUnits) : null),
    [unitFilter, orgUnits],
  );

  const filtersActive = !!nameFilter || !!roleFilter || !!unitFilter;

  const visibleEmployeeIds = useMemo(() => {
    if (!filtersActive) return null;
    const ids = new Set<string>();
    for (const e of employees) {
      if (matchesFilters(e, nameFilter, roleFilter, unitFilterIds)) ids.add(e.id);
    }
    return ids;
  }, [employees, nameFilter, roleFilter, unitFilterIds, filtersActive]);

  // При активных фильтрах разворачиваем цепочку предков каждого
  // подразделения, где нашёлся хоть один подходящий сотрудник — иначе
  // совпадение будет "не видно" за свёрнутым родителем.
  const forceExpanded = useMemo(() => {
    const ids = new Set<string>();
    if (!filtersActive || !visibleEmployeeIds || !orgUnits) return ids;
    const parentOf = new Map(orgUnits.map((u) => [u.id, u.parent_id]));
    for (const e of employees) {
      if (!visibleEmployeeIds.has(e.id) || !e.org_unit_id) continue;
      let cur: string | null = e.org_unit_id;
      while (cur && !ids.has(cur)) {
        ids.add(cur);
        cur = parentOf.get(cur) ?? null;
      }
    }
    return ids;
  }, [filtersActive, visibleEmployeeIds, employees, orgUnits]);

  function toggleExpanded(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function expandAll() {
    setExpanded(new Set((orgUnits ?? []).map((u) => u.id)));
  }

  function collapseAll() {
    setExpanded(new Set());
  }

  const unassignedVisible = unassigned.filter((e) => !visibleEmployeeIds || visibleEmployeeIds.has(e.id));
  const showUnassigned = unassignedVisible.length > 0 && (!unitFilter || !filtersActive);

  return (
    <div>
      <h3>Оргструктура и сотрудники</h3>
      <p style={{ color: "#888", fontSize: "0.9em" }}>
        Подразделения и сотрудники синхронизируются из внешней системы (вкладка «Синхронизация») —
        здесь можно скорректировать вручную: сопоставление с подразделением, льготы, табельный
        номер, роль HR-admin.
      </p>

      <div
        style={{
          display: "flex",
          gap: 10,
          flexWrap: "wrap",
          alignItems: "center",
          margin: "10px 0",
          padding: 8,
          background: "#fafafa",
          borderRadius: 4,
        }}
      >
        <input
          type="text"
          placeholder="Поиск по ФИО"
          value={nameFilter}
          onChange={(e) => setNameFilter(e.target.value)}
          style={{ width: 200 }}
        />
        <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
          <option value="">Все роли</option>
          <option value="employee">Сотрудник</option>
          <option value="manager">Руководитель</option>
          <option value="hr_admin">HR-admin</option>
        </select>
        <select value={unitFilter} onChange={(e) => setUnitFilter(e.target.value)}>
          <option value="">Все подразделения</option>
          {(orgUnits ?? []).map((u) => (
            <option key={u.id} value={u.id}>
              {u.name}
            </option>
          ))}
        </select>
        <button type="button" onClick={expandAll}>
          Развернуть всё
        </button>
        <button type="button" onClick={collapseAll}>
          Свернуть всё
        </button>
      </div>

      {isHrAdmin && (
        <div style={{ marginBottom: 8, display: "flex", gap: 8 }}>
          <button type="button" onClick={() => setUnitEditState({ mode: "create", parentId: null })}>
            + подразделение
          </button>
          <button type="button" onClick={() => setCreatingEmployeeUnitId(null)}>
            + сотрудник без подразделения
          </button>
        </div>
      )}
      {isHrAdmin && unitEditState?.mode === "create" && unitEditState.parentId === null && (
        <OrgUnitForm
          orgUnits={orgUnits ?? []}
          employees={employees}
          state={unitEditState}
          onSaved={refresh}
          onCancel={() => setUnitEditState(null)}
        />
      )}
      {isHrAdmin && creatingEmployeeUnitId === null && (
        <EmployeeForm
          orgUnits={orgUnits ?? []}
          initial={null}
          defaultOrgUnitId={null}
          onSaved={refresh}
          onCancel={() => setCreatingEmployeeUnitId(undefined)}
        />
      )}

      {tree.map((node) => (
        <OrgUnitNode
          key={node.unit.id}
          node={node}
          depth={0}
          employeesByUnit={employeesByUnit}
          visibleEmployeeIds={visibleEmployeeIds}
          forceExpanded={forceExpanded}
          expanded={expanded}
          toggleExpanded={toggleExpanded}
          orgUnits={orgUnits ?? []}
          allEmployees={employees}
          isHrAdmin={isHrAdmin}
          currentUserId={currentUser?.id}
          year={year}
          unitEditState={unitEditState}
          setUnitEditState={setUnitEditState}
          editingEmployeeId={editingEmployeeId}
          setEditingEmployeeId={setEditingEmployeeId}
          creatingEmployeeUnitId={creatingEmployeeUnitId}
          setCreatingEmployeeUnitId={setCreatingEmployeeUnitId}
          onSaved={refresh}
          filtersActive={filtersActive}
        />
      ))}

      {showUnassigned && (
        <div style={{ marginTop: 16 }}>
          <div style={{ fontWeight: 600, color: "#888" }}>
            Без подразделения <span style={{ color: "#aaa" }}>[{unassignedVisible.length}]</span>
          </div>
          <ul style={{ margin: "4px 0 4px 20px", padding: 0, listStyle: "none" }}>
            {unassignedVisible.map((e) => (
              <EmployeeRow
                key={e.id}
                employee={e}
                orgUnits={orgUnits ?? []}
                isHrAdmin={isHrAdmin}
                currentUserId={currentUser?.id}
                year={year}
                editing={editingEmployeeId === e.id}
                setEditing={setEditingEmployeeId}
                onSaved={refresh}
              />
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
