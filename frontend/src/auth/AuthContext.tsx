import { useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import {
  apiFetch,
  getAdminFallbackCreds,
  getDevUserId,
  setAdminFallbackCreds,
  setDevUserId,
} from "../api/client";
import type { CurrentUserOut, UserOut } from "../api/types";

interface AuthState {
  currentUser: CurrentUserOut | null;
  devUsers: UserOut[];
  loading: boolean;
  loginAs: (userId: string) => Promise<void>;
  loginAsFallback: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [currentUser, setCurrentUser] = useState<CurrentUserOut | null>(null);
  const [devUsers, setDevUsers] = useState<UserOut[]>([]);
  const [loading, setLoading] = useState(true);

  const refreshMe = async () => {
    if (!getDevUserId() && !getAdminFallbackCreds()) {
      setCurrentUser(null);
      return;
    }
    try {
      const me = await apiFetch<CurrentUserOut>("/users/me");
      setCurrentUser(me);
    } catch {
      setDevUserId(null);
      setAdminFallbackCreds(null);
      setCurrentUser(null);
    }
  };

  useEffect(() => {
    (async () => {
      try {
        const users = await apiFetch<UserOut[]>("/auth/dev/users");
        setDevUsers(users);
      } catch {
        // Недоступно вне dev-режима (auth_provider=kerberos) — ожидаемо,
        // не должно блокировать остальную инициализацию (см. ниже).
      }
      await refreshMe();
      setLoading(false);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Смена пользователя (dev-логин) не должна оставлять в кэше React Query
  // данные предыдущего — иначе на миг просачиваются чужие/недоступные
  // данные (или запросы к ним падают 403, пока кэш не обновится сам).
  const loginAs = async (userId: string) => {
    setDevUserId(userId);
    queryClient.clear();
    await refreshMe();
  };

  // Аварийный вход hr_admin — работает независимо от auth_provider (см.
  // backend app/auth/admin_fallback.py). В отличие от refreshMe() ошибку не
  // проглатываем, а пробрасываем — форме входа нужно показать "неверный
  // пароль", а не молча остаться на экране логина.
  const loginAsFallback = async (email: string, password: string) => {
    setAdminFallbackCreds({ email, password });
    try {
      const me = await apiFetch<CurrentUserOut>("/users/me");
      queryClient.clear();
      setCurrentUser(me);
    } catch (err) {
      setAdminFallbackCreds(null);
      throw err;
    }
  };

  const logout = () => {
    setDevUserId(null);
    setAdminFallbackCreds(null);
    setCurrentUser(null);
    queryClient.clear();
  };

  return (
    <AuthContext.Provider
      value={{ currentUser, devUsers, loading, loginAs, loginAsFallback, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
