import { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { ApprovalQueuePage } from "./ApprovalQueuePage";
import { roleLabel } from "./DevLoginPage";
import { MyRequestsPage } from "./MyRequestsPage";
import { OrgUnitsPage } from "./OrgUnitsPage";
import { RequestFormPage } from "./RequestFormPage";

type Tab = "my-requests" | "new-request" | "approvals" | "org-units";

export function HomePage() {
  const { currentUser, logout } = useAuth();
  const [tab, setTab] = useState<Tab>("my-requests");

  if (!currentUser) return null;

  const tabs: { id: Tab; label: string; visible: boolean }[] = [
    { id: "my-requests", label: "Мои заявки", visible: true },
    { id: "new-request", label: "Новая заявка", visible: true },
    { id: "approvals", label: "Согласование", visible: currentUser.role !== "employee" },
    { id: "org-units", label: "Оргструктура", visible: true },
  ];

  return (
    <div style={{ maxWidth: 720, margin: "2rem auto", fontFamily: "sans-serif" }}>
      <h1>Планирование отпусков</h1>
      <p>
        Вы вошли как <strong>{currentUser.full_name}</strong> ({roleLabel(currentUser.role)})
        {currentUser.has_benefits && " — есть льготы"}
      </p>
      <button onClick={logout}>Выйти</button>

      <nav style={{ display: "flex", gap: 8, margin: "16px 0", borderBottom: "1px solid #ccc" }}>
        {tabs
          .filter((t) => t.visible)
          .map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              style={{
                padding: "6px 12px",
                fontWeight: tab === t.id ? "bold" : "normal",
                background: "none",
                border: "none",
                borderBottom: tab === t.id ? "2px solid #333" : "2px solid transparent",
                cursor: "pointer",
              }}
            >
              {t.label}
            </button>
          ))}
      </nav>

      {tab === "my-requests" && <MyRequestsPage />}
      {tab === "new-request" && <RequestFormPage />}
      {tab === "approvals" && <ApprovalQueuePage />}
      {tab === "org-units" && <OrgUnitsPage />}
    </div>
  );
}
