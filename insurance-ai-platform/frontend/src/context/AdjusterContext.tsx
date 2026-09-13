import { createContext, useContext, useState, type ReactNode } from "react";

const STORAGE_KEY = "adjuster-console:acting-as";

interface AdjusterContextValue {
  adjusterId: string | null;
  setAdjusterId: (id: string | null) => void;
}

const AdjusterContext = createContext<AdjusterContextValue | undefined>(undefined);

export function AdjusterProvider({ children }: { children: ReactNode }) {
  const [adjusterId, setAdjusterIdState] = useState<string | null>(() => {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch {
      return null;
    }
  });

  const setAdjusterId = (id: string | null) => {
    setAdjusterIdState(id);
    try {
      if (id) localStorage.setItem(STORAGE_KEY, id);
      else localStorage.removeItem(STORAGE_KEY);
    } catch {
      // localStorage unavailable (private browsing, etc.) -- state still
      // updates for this session, it just won't persist across reloads.
    }
  };

  return <AdjusterContext.Provider value={{ adjusterId, setAdjusterId }}>{children}</AdjusterContext.Provider>;
}

export function useAdjusterIdentity(): AdjusterContextValue {
  const context = useContext(AdjusterContext);
  if (!context) {
    throw new Error("useAdjusterIdentity must be used within an AdjusterProvider");
  }
  return context;
}
