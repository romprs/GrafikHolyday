import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { apiFetch } from "../api/client";
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

function OrgUnitNode({
  node,
  employeesByUnit,
  employeesById,
  depth,
}: {
  node: TreeNode;
  employeesByUnit: Map<string, OrgUnitEmployeeOut[]>;
  employeesById: Map<string, OrgUnitEmployeeOut>;
  depth: number;
}) {
  const employees = employeesByUnit.get(node.unit.id) ?? [];
  const head = node.unit.head_user_id ? employeesById.get(node.unit.head_user_id) : undefined;

  return (
    <div style={{ marginLeft: depth === 0 ? 0 : 20, marginTop: 8 }}>
      <div style={{ fontWeight: 600 }}>
        {node.unit.name}
        {node.unit.unit_kind && (
          <span style={{ fontWeight: 400, color: "#888" }}> ({node.unit.unit_kind})</span>
        )}
        {head && <span style={{ fontWeight: 400, color: "#888" }}> — рук. {head.full_name}</span>}
      </div>
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
          depth={depth + 1}
        />
      ))}
    </div>
  );
}

export function OrgUnitsPage() {
  const { data: orgUnits } = useQuery({
    queryKey: ["org-units"],
    queryFn: () => apiFetch<OrgUnitOut[]>("/org-units"),
  });
  const { data: employees } = useQuery({
    queryKey: ["org-unit-employees"],
    queryFn: () => apiFetch<OrgUnitEmployeeOut[]>("/org-units/employees"),
  });

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
      {tree.map((node) => (
        <OrgUnitNode
          key={node.unit.id}
          node={node}
          employeesByUnit={employeesByUnit}
          employeesById={employeesById}
          depth={0}
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
