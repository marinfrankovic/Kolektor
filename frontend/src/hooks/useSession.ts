import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, type SetupStatus, type User } from "../api/client";
import type { Language } from "../i18n/dictionaries";

export type Session = {
  user: User | null;
  setup: SetupStatus;
  language: Language;
  authMode: SetupStatus["auth_mode"];
  needsSetup: boolean;
  needsLogin: boolean;
};

const STORED_LANGUAGE_KEY = "kolektor.language";

export function storedLanguage(): Language | null {
  const value = localStorage.getItem(STORED_LANGUAGE_KEY);
  return value === "en" || value === "hr" ? value : null;
}

export function storeLanguage(language: Language) {
  localStorage.setItem(STORED_LANGUAGE_KEY, language);
}

export function useSession() {
  return useQuery<Session>({
    queryKey: ["session"],
    retry: false,
    staleTime: 30_000,
    queryFn: async () => {
      const setup = await api.setupStatus();

      if (setup.setup_required) {
        return {
          user: null,
          setup,
          language: storedLanguage() ?? setup.default_language,
          authMode: setup.auth_mode,
          needsSetup: true,
          needsLogin: false,
        };
      }

      let user: User | null = null;
      try {
        user = await api.me();
      } catch (error) {
        // 401 in password mode simply means nobody is signed in yet.
        if (!(error instanceof ApiError) || error.status !== 401) throw error;
      }

      return {
        user,
        setup,
        language: user?.language ?? storedLanguage() ?? setup.default_language,
        authMode: setup.auth_mode,
        needsSetup: false,
        needsLogin: user === null,
      };
    },
  });
}

export function useRefreshSession() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["session"] });
}
