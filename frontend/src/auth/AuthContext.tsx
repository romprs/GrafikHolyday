import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { apiFetch, getDevUserId, setDevUserId } from "../api/client";
import type { CurrentUserOut, UserOut } from "../api/types";

interface AuthState {
  currentUser: CurrentUserOut | null;
  devUsers: UserOut[];
  loading: boolean;
  loginAs: (userId: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [currentUser, setCurrentUser] = useState<CurrentUserOut | null>(null);
  const [devUsers, setDevUsers] = useState<UserOut[]>([]);
  const [loading, setLoading] = useState(true);

  const refreshMe = async () => {
    if (!getDevUserId()) {
      setCurrentUser(null);
      return;
    }
    try {
      const me = await apiFetch<CurrentUserOut>("/users/me");
      setCurrentUser(me);
    } catch {
      setDevUserId(null);
      setCurrentUser(null);
    }
  };

  useEffect(() => {
    (async () => {
      const users = await apiFetch<UserOut[]>("/auth/dev/users");
      setDevUsers(users);
      await refreshMe();
      setLoading(false);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loginAs = async (userId: string) => {
    setDevUserId(userId);
    await refreshMe();
  };

  const logout = () => {
    setDevUserId(null);
    setCurrentUser(null);
  };

  return (
    <AuthContext.Provider value={{ currentUser, devUsers, loading, loginAs, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
