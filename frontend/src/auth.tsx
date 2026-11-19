import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api, getToken, Role, setToken, setUnauthorizedHandler } from "./api";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
}

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  can: (...roles: Role[]) => boolean;
}

const AuthContext = createContext<AuthState>(null as unknown as AuthState);
export const useAuth = () => useContext(AuthContext);

// Role groups mirror the backend permission sets.
export const MANAGE: Role[] = ["admin", "procurement_manager"];
export const REQUISITION_WRITE: Role[] = ["admin", "procurement_manager", "requester"];
export const APPROVE: Role[] = ["admin", "procurement_manager", "approver"];
export const ANALYTICS: Role[] = ["admin", "procurement_manager", "approver", "viewer"];

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(!!getToken());

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    if (getToken()) {
      api
        .get("/auth/me")
        .then(setUser)
        .catch(logout)
        .finally(() => setLoading(false));
    }
  }, [logout]);

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await api.login(email, password);
    setToken(access_token);
    setUser(await api.get("/auth/me"));
  }, []);

  const value = useMemo<AuthState>(
    () => ({ user, loading, login, logout, can: (...roles) => !!user && roles.includes(user.role) }),
    [user, loading, login, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
