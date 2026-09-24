import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { getRestrictionSettings } from "../api/calendar";
import { listMyDelegationTargets } from "../api/delegations";
import { listMyLeaveRequests } from "../api/leaveRequests";
import { NavIcon, type NavIconKey } from "../navIcons";
import { useTheme } from "../useTheme";
import { AllRequestsPage } from "./AllRequestsPage";
import { ApprovalQueuePage } from "./ApprovalQueuePage";
import { AuditLogPage } from "./AuditLogPage";
import { BlockedPeriodsPage } from "./BlockedPeriodsPage";
import { DelegationsPage } from "./DelegationsPage";
import { roleLabel } from "./DevLoginPage";
import { IntegrationsSettingsPage } from "./IntegrationsSettingsPage";
import { MyRequestsPage } from "./MyRequestsPage";
import { OrgDirectoryPage } from "./OrgDirectoryPage";
import { OrgLoadDashboardPage } from "./OrgLoadDashboardPage";
import { RequestFormPage } from "./RequestFormPage";
import { RestrictionSettingsPage } from "./RestrictionSettingsPage";
import { SyncPage } from "./SyncPage";

type Tab =
  | "my-requests"
  | "new-request"
  | "approvals"
  | "blocked-periods"
  | "org-directory"
  | "org-load"
  | "delegations"
  | "sync"
  | "restriction-settings"
  | "integrations"
  | "all-requests"
  | "audit-log";

export function HomePage() {
  const { currentUser, logout } = useAuth();
  const [tab, setTab] = useState<Tab>("my-requests");
  const [theme, toggleTheme] = useTheme();

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
  // Делегат может подавать заявки за подопечных даже когда у него самого
  // уже есть активная заявка — вкладку нельзя прятать только по своему
  // статусу, если есть за кого ещё подать (см. onBehalfOf в RequestFormPage).
  const { data: delegationTargets } = useQuery({
    queryKey: ["delegation-targets"],
    queryFn: listMyDelegationTargets,
    enabled: !!currentUser,
  });

  const planningYearSetting = restrictionSettings?.find((s) => s.key === "planning_year");
  const planningYear =
    typeof planningYearSetting?.params.year === "number"
      ? planningYearSetting.params.year
      : new Date().getFullYear();

  // Пока есть поданная или согласованная заявка на плановый год — новую
  // за себя начинать нельзя (см. leave_request_service._check_no_active_submission).
  const hasActiveSubmissionThisYear = (myRequests ?? []).some(
    (r) =>
      (r.status === "pending_approval" || r.status === "approved") &&
      new Date(r.date_from).getFullYear() <= planningYear &&
      new Date(r.date_to).getFullYear() >= planningYear,
  );
  const canSubmitNewRequest = !hasActiveSubmissionThisYear || (delegationTargets?.length ?? 0) > 0;

  useEffect(() => {
    if (tab === "new-request" && !canSubmitNewRequest) {
      setTab("my-requests");
    }
  }, [tab, canSubmitNewRequest]);

  if (!currentUser) return null;

  const isManager = currentUser.role === "manager";
  const isHrAdmin = currentUser.role === "hr_admin";
  const isManagerOrHr = isManager || isHrAdmin;
  // role — это ПРИОРИТЕТ (hr_admin перекрывает manager на бэкенде), поэтому
  // HR-admin, который одновременно возглавляет подразделение, не совпадает
  // с isManager — без отдельного флага не увидел бы согласование по своим
  // же подчинённым. is_approver — то же самое для заместителя руководителя,
  // которому право согласования выдано вручную (см. OrgDirectoryPage).
  const canApproveOwnTeam = isManager || currentUser.is_org_unit_head || currentUser.is_approver;

  // HR-админ — такой же сотрудник, как и все, и тоже уходит в отпуск: сам
  // подаёт заявки на общих основаниях (согласовывает их его руководитель,
  // если он есть, — админ-роль на это не влияет).
  const tabs: { id: Tab; label: string; visible: boolean; icon: NavIconKey; group?: string }[] = [
    { id: "my-requests", label: "Мои заявки", visible: true, icon: "doc" },
    { id: "new-request", label: "Новая заявка", visible: canSubmitNewRequest, icon: "plus" },
    { id: "approvals", label: "Согласование", visible: canApproveOwnTeam, icon: "star", group: "Подразделение" },
    { id: "blocked-periods", label: "Недоступные периоды", visible: isManagerOrHr, icon: "lock", group: "Подразделение" },
    { id: "org-directory", label: "Оргструктура и сотрудники", visible: isManagerOrHr, icon: "users", group: "Подразделение" },
    { id: "org-load", label: "Отпуска подразделений", visible: isManagerOrHr, icon: "grid", group: "Подразделение" },
    { id: "delegations", label: "Делегирование", visible: isManagerOrHr, icon: "swap", group: "Подразделение" },
    { id: "sync", label: "Синхронизация", visible: isHrAdmin, icon: "sync", group: "Администрирование" },
    { id: "restriction-settings", label: "Ограничения", visible: isHrAdmin, icon: "sliders", group: "Администрирование" },
    { id: "integrations", label: "Интеграции", visible: isHrAdmin, icon: "plug", group: "Администрирование" },
    { id: "all-requests", label: "Все заявки", visible: isHrAdmin, icon: "all", group: "Администрирование" },
    { id: "audit-log", label: "Журнал изменений", visible: isHrAdmin, icon: "clock", group: "Администрирование" },
  ];

  const visibleTabs = tabs.filter((t) => t.visible);
  const groupOrder = [undefined, "Подразделение", "Администрирование"] as const;

  return (
    <div className="app-shell">
      <aside className="app-rail">
        <div className="app-brand">
          <span className="dot" />
          <span>Отпуска</span>
        </div>
        <nav>
          {groupOrder.map((group) => {
            const items = visibleTabs.filter((t) => t.group === group);
            if (items.length === 0) return null;
            const Icon = (key: NavIconKey) => NavIcon[key];
            return (
              <div className="rail-group" key={group ?? "base"}>
                {group && <div className="gtitle">{group}</div>}
                {items.map((t) => {
                  const IconComp = Icon(t.icon);
                  return (
                    <button
                      key={t.id}
                      type="button"
                      className={`navlink${tab === t.id ? " on" : ""}`}
                      onClick={() => setTab(t.id)}
                    >
                      <IconComp />
                      {t.label}
                    </button>
                  );
                })}
              </div>
            );
          })}
        </nav>
        <div className="who">
          <strong>{currentUser.full_name}</strong>
          <br />
          {roleLabel(currentUser.role)}
          {currentUser.has_benefits && " · есть льготы"}
          <button type="button" className="btn-ghost logout" onClick={logout} style={{ padding: "4px 0" }}>
            Выйти
          </button>
          <button type="button" className="theme-toggle" onClick={toggleTheme}>
            {theme === "light" ? "🌙 Тёмная тема" : "☀ Светлая тема"}
          </button>
        </div>
      </aside>
      <main className="app-main">
        {tab === "my-requests" && <MyRequestsPage />}
        {tab === "new-request" && <RequestFormPage />}
        {tab === "approvals" && <ApprovalQueuePage />}
        {tab === "blocked-periods" && <BlockedPeriodsPage />}
        {tab === "org-directory" && <OrgDirectoryPage />}
        {tab === "org-load" && <OrgLoadDashboardPage />}
        {tab === "delegations" && <DelegationsPage />}
        {tab === "sync" && <SyncPage />}
        {tab === "restriction-settings" && <RestrictionSettingsPage />}
        {tab === "integrations" && <IntegrationsSettingsPage />}
        {tab === "all-requests" && <AllRequestsPage />}
        {tab === "audit-log" && <AuditLogPage />}
      </main>
    </div>
  );
}
