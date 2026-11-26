import { useQuery } from "@tanstack/react-query";
import { useCallback, useSyncExternalStore } from "react";
import { useNavigate } from "react-router-dom";
import { fetchMe } from "@/lib/api";
import { clearToken, getToken, setToken, TOKEN_KEY } from "@/lib/auth";

const listeners = new Set<() => void>();

function subscribe(listener: () => void) {
  listeners.add(listener);
  const onStorage = (event: StorageEvent) => {
    if (event.key === TOKEN_KEY || event.key === null) listener();
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

function emit() {
  listeners.forEach((listener) => listener());
}

export function useAuth() {
  const navigate = useNavigate();
  const token = useSyncExternalStore(
    subscribe,
    () => getToken(),
    () => null,
  );

  const me = useQuery({
    queryKey: ["me", token],
    queryFn: () => fetchMe(token!),
    enabled: Boolean(token),
    retry: false,
  });

  const loginSuccess = useCallback(
    (accessToken: string, redirectTo = "/") => {
      setToken(accessToken);
      emit();
      navigate(redirectTo);
    },
    [navigate],
  );

  const logout = useCallback(() => {
    clearToken();
    emit();
    navigate("/login");
  }, [navigate]);

  return {
    token,
    user: me.data ?? null,
    isLoading: Boolean(token) && me.isLoading,
    isError: me.isError,
    loginSuccess,
    logout,
    refresh: me.refetch,
  };
}
