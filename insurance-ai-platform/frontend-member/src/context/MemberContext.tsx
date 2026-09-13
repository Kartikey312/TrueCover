import { createContext, useContext, useState, type ReactNode } from "react";

const STORAGE_KEY = "member-portal:signed-in-as";

interface MemberContextValue {
  memberId: string | null;
  setMemberId: (id: string | null) => void;
}

const MemberContext = createContext<MemberContextValue | undefined>(undefined);

export function MemberProvider({ children }: { children: ReactNode }) {
  const [memberId, setMemberIdState] = useState<string | null>(() => {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch {
      return null;
    }
  });

  const setMemberId = (id: string | null) => {
    setMemberIdState(id);
    try {
      if (id) localStorage.setItem(STORAGE_KEY, id);
      else localStorage.removeItem(STORAGE_KEY);
    } catch {
      // localStorage unavailable -- state still updates for this session
    }
  };

  return <MemberContext.Provider value={{ memberId, setMemberId }}>{children}</MemberContext.Provider>;
}

export function useMemberIdentity(): MemberContextValue {
  const context = useContext(MemberContext);
  if (!context) {
    throw new Error("useMemberIdentity must be used within a MemberProvider");
  }
  return context;
}
