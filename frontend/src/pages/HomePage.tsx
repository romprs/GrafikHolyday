import { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { AllRequestsPage } from "./AllRequestsPage";
import { ApprovalQueuePage } from "./ApprovalQueuePage";
import { AuditLogPage } from "./AuditLogPage";
import { BlockedPeriodsPage } from "./BlockedPeriodsPage";
import { roleLabel } from "./DevLoginPage";
import { EmployeesPage } from "./EmployeesPage";
import { IntegrationsSettingsPage } from "./IntegrationsSettingsPage";
import { MyRequestsPage } from "./MyRequestsPage";
import { OrgLoadDashboardPage } from "./OrgLoadDashboardPage";
import { OrgUnitsPage } from "./OrgUnitsPage";
import { RequestFormPage } from "./RequestFormPage";
import { RestrictionSettingsPage } from "./RestrictionSettingsPage";
import { RolesPage } from "./RolesPage";
import { SyncPage } from "./SyncPage";
import { TeamCalendarPage } from "./TeamCalendarPage";

type Tab =
  | "my-requests"
  | "new-request"
  | "approvals"
  | "team-calendar"
  | "blocked-periods"
  | "org-units"
  | "org-load"
  | "sync"
  | "restriction-settings"
  | "integrations"
  | "all-requests"
  | "audit-log"
  | "employees"
  | "roles";

export function HomePage() {
  const { currentUser, logout } = useAuth();
  const [tab, setTab] = useState<Tab>("my-requests");

  if (!currentUser) return null;

  const isManagerOrHr = currentUser.role !== "employee";
  const isHrAdmin = currentUser.role === "hr_admin";

  const tabs: { id: Tab; label: string; visible: boolean }[] = [
    { id: "my-requests", label: "Мои заявки", visible: true },
    { id: "new-request", label: "Новая заявка", visible: true },
    { id: "approvals", label: "Согласование", visible: isManagerOrHr },
    { id: "team-calendar", label: "Календарь отдела", visible: true },
    { id: "blocked-periods", label: "Недоступные периоды", visible: isManagerOrHr },
    { id: "org-units", label: "Оргструктура", visible: true },
    { id: "org-load", label: "Загруженность отделов", visible: isManagerOrHr },
    { id: "sync", label: "Синхронизация", visible: isHrAdmin },
    { id: "restriction-settings", label: "Ограничения", visible: isHrAdmin },
    { id: "integrations", label: "Интеграции", visible: isHrAdmin },
    { id: "all-requests", label: "Все заявки", visible: isHrAdmin },
    { id: "audit-log", label: "Журнал изменений", visible: isHrAdmin },
    { id: "employees", label: "Сотрудники", visible: isHrAdmin },
    { id: "roles", label: "Роли", visible: isHrAdmin },
  ];

  return (
    <div style={{ maxWidth: 1440, margin: "2rem auto", fontFamily: "sans-serif", padding: "0 16px" }}>
      <h1>Планирование отпусков</h1>
      <p>
        Вы вошли как <strong>{currentUser.full_name}</strong> ({roleLabel(currentUser.role)})
        {currentUser.has_benefits && " — есть льготы"}
      </p>
      <button onClick={logout}>Выйти</button>

      <nav style={{ display: "flex", gap: 8, margin: "16px 0", borderBottom: "1px solid #ccc", flexWrap: "wrap" }}>
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
      {tab === "team-calendar" && <TeamCalendarPage />}
      {tab === "blocked-periods" && <BlockedPeriodsPage />}
      {tab === "org-units" && <OrgUnitsPage />}
      {tab === "org-load" && <OrgLoadDashboardPage />}
      {tab === "sync" && <SyncPage />}
      {tab === "restriction-settings" && <RestrictionSettingsPage />}
      {tab === "integrations" && <IntegrationsSettingsPage />}
      {tab === "all-requests" && <AllRequestsPage />}
      {tab === "audit-log" && <AuditLogPage />}
      {tab === "employees" && <EmployeesPage />}
      {tab === "roles" && <RolesPage />}
    </div>
  );
}
