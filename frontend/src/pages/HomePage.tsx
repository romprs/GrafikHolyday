import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { getRestrictionSettings } from "../api/calendar";
import { listMyLeaveRequests } from "../api/leaveRequests";
import { AllRequestsPage } from "./AllRequestsPage";
import { ApprovalQueuePage } from "./ApprovalQueuePage";
import { AuditLogPage } from "./AuditLogPage";
import { BlockedPeriodsPage } from "./BlockedPeriodsPage";
import { DelegationsPage } from "./DelegationsPage";
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
  | "delegations"
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

  const { data: restrictionSettings } = useQuery({
    queryKey: ["restriction-settings"],
    queryFn: getRestrictionSettings,
    enabled: !!currentUser,
  });
  const { data: myRequests } = useQuery({
    queryKey: ["my-leave-requests"],
    queryFn: () => listMyLeaveRequests(),
    enabled: !!currentUser,
  });

  const planningYearSetting = restrictionSettings?.find((s) => s.key === "planning_year");
  const planningYear =
    typeof planningYearSetting?.params.year === "number"
      ? planningYearSetting.params.year
      : new Date().getFullYear();

  // Пока есть поданная или согласованная заявка на плановый год — новую
  // начинать нельзя (см. leave_request_service._check_no_active_submission),
  // поэтому вкладку скрываем совсем, а не просто блокируем форму внутри.
  const hasActiveSubmissionThisYear = (myRequests ?? []).some(
    (r) =>
      (r.status === "pending_approval" || r.status === "approved") &&
      new Date(r.date_from).getFullYear() <= planningYear &&
      new Date(r.date_to).getFullYear() >= planningYear,
  );

  useEffect(() => {
    if (tab === "new-request" && hasActiveSubmissionThisYear) {
      setTab("my-requests");
    }
  }, [tab, hasActiveSubmissionThisYear]);

  // HR-админ по умолчанию попал бы на скрытую для него вкладку "Мои
  // заявки" — переключаем на первую доступную, как только известна роль.
  useEffect(() => {
    if (currentUser?.role === "hr_admin" && (tab === "my-requests" || tab === "team-calendar")) {
      setTab("employees");
    }
  }, [currentUser?.role, tab]);

  if (!currentUser) return null;

  const isManager = currentUser.role === "manager";
  const isHrAdmin = currentUser.role === "hr_admin";
  const isManagerOrHr = isManager || isHrAdmin;

  // HR-админ заявки на отпуск сам не подаёт и не согласовывает через этот
  // интерфейс (для этого есть admin-override и делегирование) — поэтому
  // сотруднические вкладки ему не показываем.
  const tabs: { id: Tab; label: string; visible: boolean }[] = [
    { id: "my-requests", label: "Мои заявки", visible: !isHrAdmin },
    { id: "new-request", label: "Новая заявка", visible: !isHrAdmin && !hasActiveSubmissionThisYear },
    { id: "approvals", label: "Согласование", visible: isManager },
    { id: "team-calendar", label: "Календарь отдела", visible: !isHrAdmin },
    { id: "blocked-periods", label: "Недоступные периоды", visible: isManagerOrHr },
    { id: "org-units", label: "Оргструктура", visible: isManagerOrHr },
    { id: "org-load", label: "Загруженность отделов", visible: isManagerOrHr },
    { id: "delegations", label: "Делегирование", visible: isManagerOrHr },
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
      {tab === "delegations" && <DelegationsPage />}
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
