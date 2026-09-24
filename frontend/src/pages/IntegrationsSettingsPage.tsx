import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import {
  clearStudyPeriodsRuns,
  clearVacationDaysRuns,
  importStudyPeriodsFile,
  listStudyPeriodsRuns,
  listVacationDaysRuns,
  testStudyPeriodsConnection,
  triggerStudyPeriodsSync,
  triggerVacationDaysSync,
  updateRestrictionSetting,
} from "../api/admin";
import { getRestrictionSettings } from "../api/calendar";
import { ApiError } from "../api/client";
import type { StudyPeriodsTestResultOut, SyncRunOut } from "../api/types";

export function IntegrationsSettingsPage() {
  const { data: settings } = useQuery({
    queryKey: ["restriction-settings"],
    queryFn: getRestrictionSettings,
  });

  const externalSource = settings?.find((s) => s.key === "external_source_connection");
  const studyPeriods = settings?.find((s) => s.key === "study_periods_source");
  const vacationDays = settings?.find((s) => s.key === "vacation_days_source");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20, maxWidth: 600 }}>
      <h3>Настройки интеграций</h3>

      {externalSource && <ExternalSourceForm key={externalSource.key} setting={externalSource} />}
      {vacationDays && <VacationDaysSourceForm key={vacationDays.key} setting={vacationDays} />}
      {studyPeriods && <StudyPeriodsSourceForm key={studyPeriods.key} setting={studyPeriods} />}
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
      {run.error_message && (
        <div className="error-text" style={{ whiteSpace: "pre-wrap" }}>{run.error_message}</div>
      )}
      {!!s.errors?.length && (
        <ul className="error-text" style={{ margin: "2px 0 0 0", paddingLeft: 18 }}>
          {s.errors.slice(0, 5).map((e, i) => (
            <li key={i}>{e}</li>
          ))}
          {s.errors.length > 5 && <li>…и ещё {s.errors.length - 5}</li>}
        </ul>
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
  const [pollInterval, setPollInterval] = useState(
    (setting.params.poll_interval_minutes as number) ?? 0,
  );
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const [testCodes, setTestCodes] = useState("");
  const [testing, setTesting] = useState(false);
  const [testError, setTestError] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<StudyPeriodsTestResultOut[] | null>(null);

  useEffect(() => {
    setEnabled(setting.enabled);
    setMode((setting.params.mode as string) ?? "file");
    setBaseUrl((setting.params.base_url as string) ?? "");
    setAuthLogin((setting.params.auth_login as string) ?? "");
    setAuthPassword((setting.params.auth_password as string) ?? "");
    setVerifyTls(Boolean(setting.params.verify_tls));
    setPollInterval((setting.params.poll_interval_minutes as number) ?? 0);
  }, [setting]);

  const { data: runs } = useQuery({
    queryKey: ["study-periods-runs"],
    queryFn: listStudyPeriodsRuns,
  });

  async function handleTestConnection() {
    setTestError(null);
    setTestResults(null);
    const codes = testCodes
      .split(/[,\s]+/)
      .map((c) => c.trim())
      .filter(Boolean);
    if (codes.length === 0) {
      setTestError("Укажите хотя бы один табельный номер");
      return;
    }
    if (codes.length > 5) {
      setTestError("Не больше 5 табельных номеров за один тест");
      return;
    }
    setTesting(true);
    try {
      const results = await testStudyPeriodsConnection({
        base_url: baseUrl,
        auth_login: authLogin,
        auth_password: authPassword,
        verify_tls: verifyTls,
        employee_codes: codes,
      });
      setTestResults(results);
    } catch (err) {
      setTestError(err instanceof ApiError ? err.message : "Не удалось проверить подключение");
    } finally {
      setTesting(false);
    }
  }

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
          poll_interval_minutes: pollInterval,
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

  async function handleClearHistory() {
    if (!window.confirm("Удалить всю историю прогонов синхронизации учебных планов? Действие необратимо.")) {
      return;
    }
    await clearStudyPeriodsRuns();
    queryClient.invalidateQueries({ queryKey: ["study-periods-runs"] });
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
    <section className="panel">
      <h4>Источник учебных планов (недоступные периоды)</h4>
      <p className="hint">
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
          <label style={{ display: "block", marginBottom: 8 }}>
            Интервал автозапуска, мин. (0 — не запускать по расписанию, только вручную)
            <input
              type="number"
              min={0}
              value={pollInterval}
              onChange={(e) => setPollInterval(Number(e.target.value))}
              style={{ display: "block", width: 120 }}
            />
          </label>

          <div className="panel" style={{ background: "var(--tint)" }}>
            <h5 style={{ margin: "0 0 6px 0" }}>Тестовое подключение</h5>
            <p className="hint" style={{ margin: "0 0 8px 0" }}>
              Проверка на 1–5 табельных номерах без записи в БД — берёт реквизиты прямо отсюда
              (не обязательно уже сохранённые), показывает реальный сформированный запрос и сырой
              ответ источника на каждый номер.
            </p>
            <input
              type="text"
              placeholder="Табельные номера через запятую или пробел, напр. 3168, 4122"
              value={testCodes}
              onChange={(e) => setTestCodes(e.target.value)}
              style={{ width: "100%", boxSizing: "border-box", marginBottom: 6 }}
            />
            <button type="button" className="btn-outline" onClick={handleTestConnection} disabled={testing || !baseUrl.trim()}>
              {testing ? "Проверяю…" : "Проверить"}
            </button>
            {testError && <p className="error-text" style={{ fontSize: "0.85em" }}>{testError}</p>}
            {testResults && (
              <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 8 }}>
                {testResults.map((r) => (
                  <div
                    key={r.employee_code}
                    style={{
                      border: `1px solid ${r.error ? "var(--bad-fg)" : "var(--ok-fg)"}`,
                      borderRadius: 8,
                      padding: 8,
                      background: "var(--surface)",
                      fontSize: "0.85em",
                    }}
                  >
                    <div style={{ fontWeight: 700 }}>
                      Табельный номер {r.employee_code}
                      {r.http_status !== null && ` — HTTP ${r.http_status}`}
                    </div>
                    <div style={{ wordBreak: "break-all", color: "var(--ink-soft)", margin: "4px 0" }}>
                      <span className="hint">Запрос: </span>
                      {r.request_url}
                    </div>
                    {r.error ? (
                      <div className="error-text">{r.error}</div>
                    ) : (
                      <div style={{ color: "var(--ok-fg)" }}>
                        Разобрано записей: {r.parsed_entries_count}
                      </div>
                    )}
                    {r.response_body_preview && (
                      <details style={{ marginTop: 4 }}>
                        <summary className="hint" style={{ cursor: "pointer" }}>Тело ответа</summary>
                        <pre
                          style={{
                            whiteSpace: "pre-wrap",
                            wordBreak: "break-all",
                            background: "var(--tint)",
                            padding: 6,
                            borderRadius: 6,
                            margin: "4px 0 0 0",
                            maxHeight: 200,
                            overflow: "auto",
                          }}
                        >
                          {r.response_body_preview}
                        </pre>
                      </details>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      <button className="btn-primary" onClick={handleSave} disabled={saving}>
        Сохранить
      </button>
      {saved && <span style={{ marginLeft: 8, color: "var(--ok-fg)" }}>Сохранено</span>}

      <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--line)" }}>
        {mode === "http" ? (
          <button className="btn-outline" onClick={handleRunHttp} disabled={running || !enabled}>
            {running ? "Выполняется…" : "Синхронизировать сейчас"}
          </button>
        ) : (
          <label>
            <span style={{ display: "inline-block", marginRight: 8 }}>Загрузить файл:</span>
            <input type="file" accept=".json,application/json" onChange={handleFileImport} disabled={running} />
          </label>
        )}
        {runError && <p className="error-text">{runError}</p>}
        {runs && runs.length > 0 && (
          <>
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
              <button className="btn-ghost" onClick={handleClearHistory} style={{ fontSize: "0.8em" }}>
                Очистить историю
              </button>
            </div>
            <ul style={{ fontSize: "0.85em", marginTop: 4, paddingLeft: 20 }}>
              {runs.slice(0, 5).map((r) => (
                <li key={r.id}>
                  <RunSummary run={r} />
                </li>
              ))}
            </ul>
          </>
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
    <section className="panel">
      <h4>Внешний источник оргструктуры</h4>
      <p className="hint">
        Отделы и иерархия — из GetDepartments(), сотрудники — из GetEmployeers() (оба под одной
        Basic-авторизацией). Сопоставление сотрудников с подразделением и заполнение табельного
        номера — автоматически при синхронизации. Запуск синхронизации, загрузка из файла (если
        URL пока недоступен) и история — на вкладке «Синхронизация». Пока источник выключен или
        URL не задан, синк по URL использует тестовые данные — загрузка файлом от этого не
        зависит и работает всегда.
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
      <button className="btn-primary" onClick={handleSave} disabled={saving}>
        Сохранить
      </button>
      {saved && <span style={{ marginLeft: 8, color: "var(--ok-fg)" }}>Сохранено</span>}
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
  const [pollInterval, setPollInterval] = useState(
    (setting.params.poll_interval_minutes as number) ?? 0,
  );
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
    setPollInterval((setting.params.poll_interval_minutes as number) ?? 0);
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
          poll_interval_minutes: pollInterval,
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

  async function handleClearHistory() {
    if (!window.confirm("Удалить всю историю прогонов синхронизации дней отпуска? Действие необратимо.")) {
      return;
    }
    await clearVacationDaysRuns();
    queryClient.invalidateQueries({ queryKey: ["vacation-days-runs"] });
  }

  return (
    <section className="panel">
      <h4>Источник дней отпуска и льгот</h4>
      <p className="hint">
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
      <label style={{ display: "block", marginBottom: 8 }}>
        Интервал автозапуска, мин. (0 — не запускать по расписанию, только вручную)
        <input
          type="number"
          min={0}
          value={pollInterval}
          onChange={(e) => setPollInterval(Number(e.target.value))}
          style={{ display: "block", width: 120 }}
        />
      </label>

      <button className="btn-primary" onClick={handleSave} disabled={saving}>
        Сохранить
      </button>
      {saved && <span style={{ marginLeft: 8, color: "var(--ok-fg)" }}>Сохранено</span>}

      <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--line)" }}>
        <button className="btn-outline" onClick={handleRun} disabled={running || !enabled}>
          {running ? "Выполняется…" : "Синхронизировать сейчас"}
        </button>
        {running && (
          <p className="hint" style={{ marginTop: 6 }}>
            Запрос идёт по одному сотруднику за раз — на большом штате может занять несколько
            минут, не закрывайте страницу.
          </p>
        )}
        {runError && <p className="error-text">{runError}</p>}
        {runs && runs.length > 0 && (
          <>
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
              <button className="btn-ghost" onClick={handleClearHistory} style={{ fontSize: "0.8em" }}>
                Очистить историю
              </button>
            </div>
            <ul style={{ fontSize: "0.85em", marginTop: 4, paddingLeft: 20 }}>
              {runs.slice(0, 5).map((r) => (
                <li key={r.id}>
                  <RunSummary run={r} />
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </section>
  );
}

