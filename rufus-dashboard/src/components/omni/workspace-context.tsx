"use client";

import React, { createContext, useContext, useState, useCallback } from "react";

export interface OmniWorkspace {
  asin: string | null;
  brandKey: string | null;
  clientId: string | null;
  threadId: string | null;
  activeAgents: string[];
  isStreaming: boolean;
}

const defaultWorkspace: OmniWorkspace = {
  asin: null,
  brandKey: null,
  clientId: null,
  threadId: null,
  activeAgents: [],
  isStreaming: false,
};

interface OmniWorkspaceContextValue {
  workspace: OmniWorkspace;
  setWorkspace: React.Dispatch<React.SetStateAction<OmniWorkspace>>;
  setAsin: (asin: string) => void;
  setBrandKey: (bk: string) => void;
  setThreadId: (id: string | null) => void;
  addActiveAgent: (agent: string) => void;
  removeActiveAgent: (agent: string) => void;
  setStreaming: (v: boolean) => void;
  reset: () => void;
}

const OmniWorkspaceContext = createContext<OmniWorkspaceContextValue | null>(null);

export function OmniWorkspaceProvider({ children }: { children: React.ReactNode }) {
  const [workspace, setWorkspace] = useState<OmniWorkspace>(defaultWorkspace);

  const setAsin = useCallback((asin: string) => {
    setWorkspace((prev) => ({ ...prev, asin }));
  }, []);

  const setBrandKey = useCallback((bk: string) => {
    setWorkspace((prev) => ({ ...prev, brandKey: bk }));
  }, []);

  const setThreadId = useCallback((id: string | null) => {
    setWorkspace((prev) => ({ ...prev, threadId: id }));
  }, []);

  const addActiveAgent = useCallback((agent: string) => {
    setWorkspace((prev) => ({
      ...prev,
      activeAgents: Array.from(new Set([...prev.activeAgents, agent])),
    }));
  }, []);

  const removeActiveAgent = useCallback((agent: string) => {
    setWorkspace((prev) => ({
      ...prev,
      activeAgents: prev.activeAgents.filter((a) => a !== agent),
    }));
  }, []);

  const setStreaming = useCallback((v: boolean) => {
    setWorkspace((prev) => ({ ...prev, isStreaming: v }));
  }, []);

  const reset = useCallback(() => {
    setWorkspace(defaultWorkspace);
  }, []);

  return (
    <OmniWorkspaceContext.Provider
      value={{
        workspace,
        setWorkspace,
        setAsin,
        setBrandKey,
        setThreadId,
        addActiveAgent,
        removeActiveAgent,
        setStreaming,
        reset,
      }}
    >
      {children}
    </OmniWorkspaceContext.Provider>
  );
}

export function useOmniWorkspace() {
  const ctx = useContext(OmniWorkspaceContext);
  if (!ctx) {
    throw new Error("useOmniWorkspace must be used within OmniWorkspaceProvider");
  }
  return ctx;
}
