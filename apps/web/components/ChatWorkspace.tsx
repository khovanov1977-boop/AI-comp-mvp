"use client";

import { useEffect, useState } from "react";
import type { Character, CompanionContext } from "@ai-companion/shared";
import { getCompanionContext } from "../lib/api";
import { ChatWindow } from "./ChatWindow";
import { CompanionPanel } from "./CompanionPanel";

export function ChatWorkspace({ character }: { character: Character }) {
  const [context, setContext] = useState<CompanionContext | null>(null);
  const [contextError, setContextError] = useState("");

  async function refreshContext() {
    setContextError("");
    try {
      setContext(await getCompanionContext(character.id));
    } catch (error) {
      setContext(null);
      setContextError(error instanceof Error ? error.message : "Could not load companion context.");
    }
  }

  useEffect(() => {
    refreshContext();
  }, [character.id]);

  return (
    <div className="chat-layout">
      <ChatWindow characterId={character.id} onAfterSend={() => refreshContext().catch(() => setContext(null))} />
      <CompanionPanel
        character={character}
        context={context}
        contextError={contextError}
        onMemoryChange={() => refreshContext()}
      />
    </div>
  );
}
