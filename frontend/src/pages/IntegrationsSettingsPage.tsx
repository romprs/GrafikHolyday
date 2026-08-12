import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import {
  importStudyPeriodsFile,
  listStudyPeriodsRuns,
  listVacationDaysRuns,
  triggerStudyPeriodsSync,
  triggerVacationDaysSync,
  updateRestrictionSetting,
} from "../api/admin";
import { getRestrictionSettings } from "../api/calendar";
import { ApiError } from "../api/client";
import type { SyncRunOut } from "../api/types";

export function IntegrationsSettingsPage() {
  const { data: settings } = useQuery({
    queryKey: ["restriction-settings"],
    queryFn: getRestrictionSettings,
  });

  const externalSource = settings?.find((s) => s.key === "external_source_connection");
  const auth = settings?.find((s) => s.key === "auth_configuration");
  const studyPeriods = settings?.find((s) => s.key === "study_periods_source");
  const vacationDays = settings?.find((s) => s.key === "vacation_days_source");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24, maxWidth: 560 }}>
      <h3>Настройки интеграций</h3>

      {externalSource && <ExternalSourceForm key={externalSource.key} setting={externalSource} />}
      {vacationDays && <VacationDaysSourceForm key={vacationDays.key} setting={vacationDays} />}
      {studyPeriods && <StudyPeriodsSourceForm key={studyPeriods.key} setting={studyPeriods} />}
      {auth && <AuthForm key={auth.key} setting={auth} />}
    </div>
  );
}

const RUN_STATUS_LABELS: Record<string, string> = {
  running: "выполняется",
  success: "успешно",
  failed: "ошибка",
  partial: "частично",
};

function RunSummary({ run }: { run: SyncRunOut }) {
  const s = run.summary;
  return (
    <span>
      {new Date(run.started_at).toLocaleString("ru-RU")} — {RUN_STATUS_LABELS[run.status] ?? run.status}
      {s.periods_created !== undefined && (
        <>
          : создано {s.periods_created}, обновлено {s.periods_updated ?? 0}, деактивировано{" "}
          {s.periods_deactivated ?? 0}
          {!!s.employees_unmatched && `, не найдено по табельному номеру: ${s.employees_unmatched}`}
          {!!s.employees_failed && `, ошибок запроса: ${s.employees_failed}`}
        </>
      )}
      {s.balances_created !== undefined && (
        <>
          : проверено {s.employees_checked ?? 0}, начислено новых {s.balances_created}, обновлено{" "}
          {s.balances_updated ?? 0}, льготность изменена у {s.benefits_changed ?? 0}
          {!!s.employees_no_data && `, нет данных: ${s.employees_no_data}`}
          {!!s.employees_failed && `, ошибок запроса: ${s.employees_failed}`}
        </>
      )}
    </span>
  );
}

function StudyPeriodsSourceForm({
  setting,
}: {
  setting: { enabled: boolean; params: Record<string, unknown> };
}) {
  const queryClient = useQueryClient();
  const [enabled, setEnabled] = useState(setting.enabled);
  const [mode, setMode] = useState((setting.params.mode as string) ?? "file");
  const [baseUrl, setBaseUrl] = useState((setting.params.base_url as string) ?? "");
  const [authLogin, setAuthLogin] = useState((setting.params.auth_login as string) ?? "");
  const [authPassword, setAuthPassword] = useState((setting.params.auth_password as string) ?? "");
  const [verifyTls, setVerifyTls] = useState(Boolean(setting.params.verify_tls));
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    setEnabled(setting.enabled);
    setMode((setting.params.mode as string) ?? "file");
    setBaseUrl((setting.params.base_url as string) ?? "");
    setAuthLogin((setting.params.auth_login as string) ?? "");
    setAuthPassword((setting.params.auth_password as string) ?? "");
    setVerifyTls(Boolean(setting.params.verify_tls));
  }, [setting]);

  const { data: runs } = useQuery({
    queryKey: ["study-periods-runs"],
    queryFn: listStudyPeriodsRuns,
  });

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    try {
      await updateRestrictionSetting("study_periods_source", {
        enabled,
        params: {
          mode,
          base_url: baseUrl,
          auth_login: authLogin,
          auth_password: authPassword,
          verify_tls: verifyTls,
        },
      });
      queryClient.invalidateQueries({ queryKey: ["restriction-settings"] });
      setSaved(true);
    } finally {
      setSaving(false);
    }
  }

  async function handleRunHttp() {
    setRunError(null);
    setRunning(true);
    try {
      await triggerStudyPeriodsSync();
      queryClient.invalidateQueries({ queryKey: ["study-periods-runs"] });
      queryClient.invalidateQueries({ queryKey: ["blocked-periods"] });
    } catch (err) {
      setRunError(err instanceof ApiError ? err.message : "Не удалось запустить синхронизацию");
    } finally {
      setRunning(false);
    }
  }

  async function handleFileImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setRunError(null);
    setRunning(true);
    try {
      const text = await file.text();
      const raw = JSON.parse(text);
      if (!Array.isArray(raw)) throw new Error("Ожидается JSON-массив на верхнем уровне файла");
      await importStudyPeriodsFile(raw);
      queryClient.invalidateQueries({ queryKey: ["study-periods-runs"] });
      queryClient.invalidateQueries({ queryKey: ["blocked-periods"] });
    } catch (err) {
      setRunError(err instanceof ApiError ? err.message : (err as Error).message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <section style={{ border: "1px solid #ddd", borderRadius: 6, padding: 16 }}>
      <h4 style={{ marginTop: 0 }}>Источник учебных планов (недоступные периоды)</h4>
      <p style={{ fontSize: "0.85em", color: "#888" }}>
        Недоступные периоды сотрудников (обучение и т.п.) сопоставляются по табельному номеру
        (задаётся на странице «Сотрудники»). Два режима: загрузка JSON-файла вручную — доступно уже
        сейчас — или синхронизация напрямую из источника по HTTP, когда будет согласован боевой
        эндпойнт.
      </p>
      <label style={{ display: "block", marginBottom: 8 }}>
        <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />{" "}
        Интеграция включена
      </label>
      <label style={{ display: "block", marginBottom: 8 }}>
        Режим
        <select value={mode} onChange={(e) => setMode(e.target.value)} style={{ display: "block" }}>
          <option value="file">Файл (JSON, загружается вручную)</option>
          <option value="http">HTTP-источник</option>
        </select>
      </label>

      {mode === "http" && (
        <>
          <label style={{ display: "block", marginBottom: 8 }}>
            URL источника
            <input
              type="text"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://host/hs/Employee/study_plan/..."
              style={{ display: "block", width: "100%" }}
            />
          </label>
          <label style={{ display: "block", marginBottom: 8 }}>
            Логин
            <input
              type="text"
              value={authLogin}
              onChange={(e) => setAuthLogin(e.target.value)}
              style={{ display: "block", width: "100%" }}
            />
          </label>
          <label style={{ display: "block", marginBottom: 8 }}>
            Пароль
            <input
              type="password"
              value={authPassword}
              onChange={(e) => setAuthPassword(e.target.value)}
              style={{ display: "block", width: "100%" }}
            />
          </label>
          <label style={{ display: "block", marginBottom: 8 }}>
            <input
              type="checkbox"
              checked={verifyTls}
              onChange={(e) => setVerifyTls(e.target.checked)}
            />{" "}
            Проверять TLS-сертификат
          </label>
        </>
      )}

      <button onClick={handleSave} disabled={saving}>
        Сохранить
      </button>
      {saved && <span style={{ marginLeft: 8, color: "green" }}>Сохранено</span>}

      <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid #eee" }}>
        {mode === "http" ? (
          <button onClick={handleRunHttp} disabled={running || !enabled}>
            Синхронизировать сейчас
          </button>
        ) : (
          <label>
            <span style={{ display: "inline-block", marginRight: 8 }}>Загрузить файл:</span>
            <input type="file" accept=".json,application/json" onChange={handleFileImport} disabled={running} />
          </label>
        )}
        {runError && <p style={{ color: "crimson" }}>{runError}</p>}
        {runs && runs.length > 0 && (
          <ul style={{ fontSize: "0.85em", marginTop: 8, paddingLeft: 20 }}>
            {runs.slice(0, 5).map((r) => (
              <li key={r.id}>
                <RunSummary run={r} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function ExternalSourceForm({
  setting,
}: {
  setting: { enabled: boolean; params: Record<string, unknown> };
}) {
  const queryClient = useQueryClient();
  const [enabled, setEnabled] = useState(setting.enabled);
  const [departmentsUrl, setDepartmentsUrl] = useState(
    (setting.params.departments_url as string) ?? "",
  );
  const [employeesUrl, setEmployeesUrl] = useState(
    (setting.params.employees_url as string) ?? "",
  );
  const [authLogin, setAuthLogin] = useState((setting.params.auth_login as string) ?? "");
  const [authPassword, setAuthPassword] = useState((setting.params.auth_password as string) ?? "");
  const [verifyTls, setVerifyTls] = useState(Boolean(setting.params.verify_tls));
  const [pollInterval, setPollInterval] = useState(
    (setting.params.poll_interval_minutes as number) ?? 60,
  );
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setEnabled(setting.enabled);
    setDepartmentsUrl((setting.params.departments_url as string) ?? "");
    setEmployeesUrl((setting.params.employees_url as string) ?? "");
    setAuthLogin((setting.params.auth_login as string) ?? "");
    setAuthPassword((setting.params.auth_password as string) ?? "");
    setVerifyTls(Boolean(setting.params.verify_tls));
    setPollInterval((setting.params.poll_interval_minutes as number) ?? 60);
  }, [setting]);

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    try {
      await updateRestrictionSetting("external_source_connection", {
        enabled,
        params: {
          departments_url: departmentsUrl,
          employees_url: employeesUrl,
          auth_login: authLogin,
          auth_password: authPassword,
          verify_tls: verifyTls,
          poll_interval_minutes: pollInterval,
        },
      });
      queryClient.invalidateQueries({ queryKey: ["restriction-settings"] });
      setSaved(true);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section style={{ border: "1px solid #ddd", borderRadius: 6, padding: 16 }}>
      <h4 style={{ marginTop: 0 }}>Внешний источник оргструктуры</h4>
      <p style={{ fontSize: "0.85em", color: "#888" }}>
        Отделы и иерархия — из GetDepartments(), сотрудники — из GetEmployeers() (оба под одной
        Basic-авторизацией). Сопоставление сотрудников с подразделением и заполнение табельного
        номера — автоматически при синхронизации. Запуск синхронизации и история — на вкладке
        «Синхронизация». Пока источник выключен или URL не задан, синк использует тестовые данные.
      </p>
      <label style={{ display: "block", marginBottom: 8 }}>
        <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />{" "}
        Источник включён
      </label>
      <label style={{ display: "block", marginBottom: 8 }}>
        URL GetDepartments()
        <input
          type="text"
          value={departmentsUrl}
          onChange={(e) => setDepartmentsUrl(e.target.value)}
          placeholder="https://host/Integration/odata/Integration/GetDepartments()"
          style={{ display: "block", width: "100%" }}
        />
      </label>
      <label style={{ display: "block", marginBottom: 8 }}>
        URL GetEmployeers()
        <input
          type="text"
          value={employeesUrl}
          onChange={(e) => setEmployeesUrl(e.target.value)}
          placeholder="https://host/Integration/odata/Integration/GetEmployeers()"
          style={{ display: "block", width: "100%" }}
        />
      </label>
      <label style={{ display: "block", marginBottom: 8 }}>
        Логин
        <input
          type="text"
          value={authLogin}
          onChange={(e) => setAuthLogin(e.target.value)}
          style={{ display: "block", width: "100%" }}
        />
      </label>
      <label style={{ display: "block", marginBottom: 8 }}>
        Пароль
        <input
          type="password"
          value={authPassword}
          onChange={(e) => setAuthPassword(e.target.value)}
          style={{ display: "block", width: "100%" }}
        />
      </label>
      <label style={{ display: "block", marginBottom: 8 }}>
        <input type="checkbox" checked={verifyTls} onChange={(e) => setVerifyTls(e.target.checked)} />{" "}
        Проверять TLS-сертификат
      </label>
      <label style={{ display: "block", marginBottom: 8 }}>
        Интервал синхронизации, мин.
        <input
          type="number"
          min={5}
          value={pollInterval}
          onChange={(e) => setPollInterval(Number(e.target.value))}
          style={{ display: "block", width: 120 }}
        />
      </label>
      <button onClick={handleSave} disabled={saving}>
        Сохранить
      </button>
      {saved && <span style={{ marginLeft: 8, color: "green" }}>Сохранено</span>}
    </section>
  );
}

function VacationDaysSourceForm({
  setting,
}: {
  setting: { enabled: boolean; params: Record<string, unknown> };
}) {
  const queryClient = useQueryClient();
  const [enabled, setEnabled] = useState(setting.enabled);
  const [baseUrl, setBaseUrl] = useState((setting.params.base_url as string) ?? "");
  const [authLogin, setAuthLogin] = useState((setting.params.auth_login as string) ?? "");
  const [authPassword, setAuthPassword] = useState((setting.params.auth_password as string) ?? "");
  const [verifyTls, setVerifyTls] = useState(Boolean(setting.params.verify_tls));
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    setEnabled(setting.enabled);
    setBaseUrl((setting.params.base_url as string) ?? "");
    setAuthLogin((setting.params.auth_login as string) ?? "");
    setAuthPassword((setting.params.auth_password as string) ?? "");
    setVerifyTls(Boolean(setting.params.verify_tls));
  }, [setting]);

  const { data: runs } = useQuery({
    queryKey: ["vacation-days-runs"],
    queryFn: listVacationDaysRuns,
  });

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    try {
      await updateRestrictionSetting("vacation_days_source", {
        enabled,
        params: {
          base_url: baseUrl,
          auth_login: authLogin,
          auth_password: authPassword,
          verify_tls: verifyTls,
        },
      });
      queryClient.invalidateQueries({ queryKey: ["restriction-settings"] });
      setSaved(true);
    } finally {
      setSaving(false);
    }
  }

  async function handleRun() {
    setRunError(null);
    setRunning(true);
    try {
      await triggerVacationDaysSync();
      queryClient.invalidateQueries({ queryKey: ["vacation-days-runs"] });
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      queryClient.invalidateQueries({ queryKey: ["user-balance"] });
    } catch (err) {
      setRunError(err instanceof ApiError ? err.message : "Не удалось запустить синхронизацию");
    } finally {
      setRunning(false);
    }
  }

  return (
    <section style={{ border: "1px solid #ddd", borderRadius: 6, padding: 16 }}>
      <h4 style={{ marginTop: 0 }}>Источник дней отпуска и льгот</h4>
      <p style={{ fontSize: "0.85em", color: "#888" }}>
        Остаток дней отпуска на плановый год и признак льготника — отдельная система от
        оргструктуры/сотрудников, запрашивается по одному табельному номеру за раз (может быть
        медленно на большом штате). Сопоставление — по табельному номеру.
      </p>
      <label style={{ display: "block", marginBottom: 8 }}>
        <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />{" "}
        Источник включён
      </label>
      <label style={{ display: "block", marginBottom: 8 }}>
        URL GetVacationDaysCount
        <input
          type="text"
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
          placeholder="https://host/hs/info/GetVacationDaysCount"
          style={{ display: "block", width: "100%" }}
        />
      </label>
      <label style={{ display: "block", marginBottom: 8 }}>
        Логин
        <input
          type="text"
          value={authLogin}
          onChange={(e) => setAuthLogin(e.target.value)}
          style={{ display: "block", width: "100%" }}
        />
      </label>
      <label style={{ display: "block", marginBottom: 8 }}>
        Пароль
        <input
          type="password"
          value={authPassword}
          onChange={(e) => setAuthPassword(e.target.value)}
          style={{ display: "block", width: "100%" }}
        />
      </label>
      <label style={{ display: "block", marginBottom: 8 }}>
        <input type="checkbox" checked={verifyTls} onChange={(e) => setVerifyTls(e.target.checked)} />{" "}
        Проверять TLS-сертификат
      </label>

      <button onClick={handleSave} disabled={saving}>
        Сохранить
      </button>
      {saved && <span style={{ marginLeft: 8, color: "green" }}>Сохранено</span>}

      <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid #eee" }}>
        <button onClick={handleRun} disabled={running || !enabled}>
          Синхронизировать сейчас
        </button>
        {runError && <p style={{ color: "crimson" }}>{runError}</p>}
        {runs && runs.length > 0 && (
          <ul style={{ fontSize: "0.85em", marginTop: 8, paddingLeft: 20 }}>
            {runs.slice(0, 5).map((r) => (
              <li key={r.id}>
                <RunSummary run={r} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function AuthForm({ setting }: { setting: { enabled: boolean; params: Record<string, unknown> } }) {
  const queryClient = useQueryClient();
  const [enabled, setEnabled] = useState(setting.enabled);
  const [mode, setMode] = useState((setting.params.mode as string) ?? "dev");
  const [issuer, setIssuer] = useState((setting.params.oidc_issuer as string) ?? "");
  const [clientId, setClientId] = useState((setting.params.oidc_client_id as string) ?? "");
  const [clientSecret, setClientSecret] = useState(
    (setting.params.oidc_client_secret as string) ?? "",
  );
  const [redirectUri, setRedirectUri] = useState(
    (setting.params.oidc_redirect_uri as string) ?? "",
  );
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setEnabled(setting.enabled);
    setMode((setting.params.mode as string) ?? "dev");
    setIssuer((setting.params.oidc_issuer as string) ?? "");
    setClientId((setting.params.oidc_client_id as string) ?? "");
    setClientSecret((setting.params.oidc_client_secret as string) ?? "");
    setRedirectUri((setting.params.oidc_redirect_uri as string) ?? "");
  }, [setting]);

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    try {
      await updateRestrictionSetting("auth_configuration", {
        enabled,
        params: {
          mode,
          oidc_issuer: issuer,
          oidc_client_id: clientId,
          oidc_client_secret: clientSecret,
          oidc_redirect_uri: redirectUri,
        },
      });
      queryClient.invalidateQueries({ queryKey: ["restriction-settings"] });
      setSaved(true);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section style={{ border: "1px solid #ddd", borderRadius: 6, padding: 16 }}>
      <h4 style={{ marginTop: 0 }}>Авторизация</h4>
      <p style={{ fontSize: "0.85em", color: "#888" }}>
        Параметры для перехода с dev-входа (выбор тестового пользователя) на реальный SSO/OIDC.
        Сохранение значений здесь фиксирует конфигурацию; сам вход через OIDC — следующий шаг,
        требующий отдельного включения на бэкенде.
      </p>
      <label style={{ display: "block", marginBottom: 8 }}>
        <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />{" "}
        Конфигурация активна
      </label>
      <label style={{ display: "block", marginBottom: 8 }}>
        Режим входа
        <select value={mode} onChange={(e) => setMode(e.target.value)} style={{ display: "block" }}>
          <option value="dev">dev (выбор тестового пользователя)</option>
          <option value="oidc">oidc (корпоративный SSO)</option>
        </select>
      </label>
      <label style={{ display: "block", marginBottom: 8 }}>
        OIDC Issuer URL
        <input
          type="text"
          value={issuer}
          onChange={(e) => setIssuer(e.target.value)}
          placeholder="https://sso.example.com/realms/company"
          style={{ display: "block", width: "100%" }}
        />
      </label>
      <label style={{ display: "block", marginBottom: 8 }}>
        Client ID
        <input
          type="text"
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          style={{ display: "block", width: "100%" }}
        />
      </label>
      <label style={{ display: "block", marginBottom: 8 }}>
        Client Secret
        <input
          type="password"
          value={clientSecret}
          onChange={(e) => setClientSecret(e.target.value)}
          style={{ display: "block", width: "100%" }}
        />
      </label>
      <label style={{ display: "block", marginBottom: 8 }}>
        Redirect URI
        <input
          type="text"
          value={redirectUri}
          onChange={(e) => setRedirectUri(e.target.value)}
          placeholder="https://vacation.example.com/auth/callback"
          style={{ display: "block", width: "100%" }}
        />
      </label>
      <button onClick={handleSave} disabled={saving}>
        Сохранить
      </button>
      {saved && <span style={{ marginLeft: 8, color: "green" }}>Сохранено</span>}
    </section>
  );
}
