import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { updateRestrictionSetting } from "../api/admin";
import { getRestrictionSettings } from "../api/calendar";

export function IntegrationsSettingsPage() {
  const { data: settings } = useQuery({
    queryKey: ["restriction-settings"],
    queryFn: getRestrictionSettings,
  });

  const externalSource = settings?.find((s) => s.key === "external_source_connection");
  const auth = settings?.find((s) => s.key === "auth_configuration");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24, maxWidth: 560 }}>
      <h3>Настройки интеграций</h3>

      {externalSource && <ExternalSourceForm key={externalSource.key} setting={externalSource} />}
      {auth && <AuthForm key={auth.key} setting={auth} />}
    </div>
  );
}

function ExternalSourceForm({
  setting,
}: {
  setting: { enabled: boolean; params: Record<string, unknown> };
}) {
  const queryClient = useQueryClient();
  const [enabled, setEnabled] = useState(setting.enabled);
  const [baseUrl, setBaseUrl] = useState((setting.params.base_url as string) ?? "");
  const [apiKey, setApiKey] = useState((setting.params.api_key as string) ?? "");
  const [pollInterval, setPollInterval] = useState(
    (setting.params.poll_interval_minutes as number) ?? 60,
  );
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setEnabled(setting.enabled);
    setBaseUrl((setting.params.base_url as string) ?? "");
    setApiKey((setting.params.api_key as string) ?? "");
    setPollInterval((setting.params.poll_interval_minutes as number) ?? 60);
  }, [setting]);

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    try {
      await updateRestrictionSetting("external_source_connection", {
        enabled,
        params: { base_url: baseUrl, api_key: apiKey, poll_interval_minutes: pollInterval },
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
        Подключение к корпоративной системе, из которой синхронизируются отделы и сотрудники.
        Пока используется тестовый (fake) клиент — реальный REST-клиент включится, когда сюда
        будут внесены боевые параметры и подключён настоящий эндпойнт.
      </p>
      <label style={{ display: "block", marginBottom: 8 }}>
        <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />{" "}
        Синхронизация включена
      </label>
      <label style={{ display: "block", marginBottom: 8 }}>
        Базовый URL
        <input
          type="text"
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
          placeholder="https://hr.example.com/api"
          style={{ display: "block", width: "100%" }}
        />
      </label>
      <label style={{ display: "block", marginBottom: 8 }}>
        API-ключ / токен
        <input
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          style={{ display: "block", width: "100%" }}
        />
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
