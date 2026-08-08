import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../api/client";
import type { OrgUnitOut } from "../api/types";

export function OrgUnitsPage() {
  const { data: orgUnits } = useQuery({
    queryKey: ["org-units"],
    queryFn: () => apiFetch<OrgUnitOut[]>("/org-units"),
  });

  return (
    <div>
      <h3>Оргструктура</h3>
      <ul>
        {orgUnits?.map((u) => (
          <li key={u.id}>
            {u.name} ({u.unit_kind})
          </li>
        ))}
      </ul>
    </div>
  );
}
