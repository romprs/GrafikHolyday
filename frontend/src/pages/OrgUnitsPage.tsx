import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { createOrgUnit, deleteOrgUnit, updateOrgUnit } from "../api/admin";
import { apiFetch, ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { OrgUnitEmployeeOut, OrgUnitOut } from "../api/types";

const ROLE_LABELS: Record<OrgUnitEmployeeOut["role"], string> = {
  employee: "сотрудник",
  manager: "руководитель",
  hr_admin: "HR-админ",
};

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

type EditState =
  | { mode: "create"; parentId: string | null }
  | { mode: "edit"; unit: OrgUnitOut };

function OrgUnitForm({
  orgUnits,
  employees,
  state,
  onSaved,
  onCancel,
}: {
  orgUnits: OrgUnitOut[];
  employees: OrgUnitEmployeeOut[];
  state: EditState;
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
        background: "#f7f7f7",
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

function OrgUnitNode({
  node,
  employeesByUnit,
  employeesById,
  allEmployees,
  orgUnits,
  depth,
  isHrAdmin,
  editState,
  setEditState,
  onSaved,
}: {
  node: TreeNode;
  employeesByUnit: Map<string, OrgUnitEmployeeOut[]>;
  employeesById: Map<string, OrgUnitEmployeeOut>;
  allEmployees: OrgUnitEmployeeOut[];
  orgUnits: OrgUnitOut[];
  depth: number;
  isHrAdmin: boolean;
  editState: EditState | null;
  setEditState: (s: EditState | null) => void;
  onSaved: () => void;
}) {
  const employees = employeesByUnit.get(node.unit.id) ?? [];
  const head = node.unit.head_user_id ? employeesById.get(node.unit.head_user_id) : undefined;
  const isEditingThis = editState?.mode === "edit" && editState.unit.id === node.unit.id;
  const isAddingChildHere = editState?.mode === "create" && editState.parentId === node.unit.id;

  async function handleDelete() {
    if (!confirm(`Деактивировать подразделение «${node.unit.name}»?`)) return;
    try {
      await deleteOrgUnit(node.unit.id);
      onSaved();
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Не удалось деактивировать подразделение");
    }
  }

  return (
    <div style={{ marginLeft: depth === 0 ? 0 : 20, marginTop: 8 }}>
      <div style={{ fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
        <span>
          {node.unit.name}
          {node.unit.unit_kind && (
            <span style={{ fontWeight: 400, color: "#888" }}> ({node.unit.unit_kind})</span>
          )}
          {head && <span style={{ fontWeight: 400, color: "#888" }}> — рук. {head.full_name}</span>}
        </span>
        {isHrAdmin && (
          <span style={{ fontWeight: 400, fontSize: "0.85em" }}>
            <button type="button" onClick={() => setEditState({ mode: "edit", unit: node.unit })}>
              изменить
            </button>{" "}
            <button
              type="button"
              onClick={() => setEditState({ mode: "create", parentId: node.unit.id })}
            >
              + подраздел
            </button>{" "}
            <button type="button" onClick={handleDelete}>
              деактивировать
            </button>
          </span>
        )}
      </div>

      {isEditingThis && (
        <OrgUnitForm
          orgUnits={orgUnits}
          employees={allEmployees}
          state={editState}
          onSaved={() => {
            setEditState(null);
            onSaved();
          }}
          onCancel={() => setEditState(null)}
        />
      )}
      {isAddingChildHere && (
        <OrgUnitForm
          orgUnits={orgUnits}
          employees={allEmployees}
          state={editState}
          onSaved={() => {
            setEditState(null);
            onSaved();
          }}
          onCancel={() => setEditState(null)}
        />
      )}

      {employees.length > 0 && (
        <ul style={{ margin: "4px 0 4px 20px", padding: 0, listStyle: "none" }}>
          {employees.map((e) => (
            <li key={e.id} style={{ color: e.role === "employee" ? "inherit" : "#2e7d32" }}>
              {e.full_name} ({e.email}){e.role !== "employee" && ` — ${ROLE_LABELS[e.role]}`}
            </li>
          ))}
        </ul>
      )}
      {node.children.map((child) => (
        <OrgUnitNode
          key={child.unit.id}
          node={child}
          employeesByUnit={employeesByUnit}
          employeesById={employeesById}
          allEmployees={allEmployees}
          orgUnits={orgUnits}
          depth={depth + 1}
          isHrAdmin={isHrAdmin}
          editState={editState}
          setEditState={setEditState}
          onSaved={onSaved}
        />
      ))}
    </div>
  );
}

export function OrgUnitsPage() {
  const { currentUser } = useAuth();
  const isHrAdmin = currentUser?.role === "hr_admin";
  const queryClient = useQueryClient();
  const { data: orgUnits } = useQuery({
    queryKey: ["org-units"],
    queryFn: () => apiFetch<OrgUnitOut[]>("/org-units"),
  });
  const { data: employees } = useQuery({
    queryKey: ["org-unit-employees"],
    queryFn: () => apiFetch<OrgUnitEmployeeOut[]>("/org-units/employees"),
  });

  const [editState, setEditState] = useState<EditState | null>(null);

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["org-units"] });
    queryClient.invalidateQueries({ queryKey: ["org-unit-employees"] });
  }

  const tree = useMemo(() => buildTree(orgUnits ?? []), [orgUnits]);
  const employeesByUnit = useMemo(() => {
    const map = new Map<string, OrgUnitEmployeeOut[]>();
    for (const e of employees ?? []) {
      if (!e.org_unit_id) continue;
      const list = map.get(e.org_unit_id) ?? [];
      list.push(e);
      map.set(e.org_unit_id, list);
    }
    for (const list of map.values()) list.sort((a, b) => a.full_name.localeCompare(b.full_name));
    return map;
  }, [employees]);
  const employeesById = useMemo(
    () => new Map((employees ?? []).map((e) => [e.id, e])),
    [employees],
  );
  const unassigned = (employees ?? []).filter((e) => !e.org_unit_id);

  return (
    <div>
      <h3>Оргструктура</h3>
      {isHrAdmin && (
        <div style={{ marginBottom: 8 }}>
          <button type="button" onClick={() => setEditState({ mode: "create", parentId: null })}>
            + добавить подразделение
          </button>
        </div>
      )}
      {isHrAdmin && editState?.mode === "create" && editState.parentId === null && (
        <OrgUnitForm
          orgUnits={orgUnits ?? []}
          employees={employees ?? []}
          state={editState}
          onSaved={() => {
            setEditState(null);
            refresh();
          }}
          onCancel={() => setEditState(null)}
        />
      )}
      {tree.map((node) => (
        <OrgUnitNode
          key={node.unit.id}
          node={node}
          employeesByUnit={employeesByUnit}
          employeesById={employeesById}
          allEmployees={employees ?? []}
          orgUnits={orgUnits ?? []}
          depth={0}
          isHrAdmin={isHrAdmin}
          editState={editState}
          setEditState={setEditState}
          onSaved={refresh}
        />
      ))}
      {unassigned.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <div style={{ fontWeight: 600, color: "#888" }}>Без подразделения</div>
          <ul style={{ margin: "4px 0 4px 20px", padding: 0, listStyle: "none" }}>
            {unassigned.map((e) => (
              <li key={e.id}>
                {e.full_name} ({e.email})
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
