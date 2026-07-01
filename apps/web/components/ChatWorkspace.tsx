"use client";

import { useEffect, useState } from "react";
import type { Character, CompanionContext } from "@ai-companion/shared";
import { getCompanionContext } from "../lib/api";
import { ChatWindow } from "./ChatWindow";
import { CompanionPanel } from "./CompanionPanel";

export function ChatWorkspace({ character }: { character: Character }) {
  const [context, setContext] = useState<CompanionContext | null>(null);

  async function refreshContext() {
    setContext(await getCompanionContext(character.id));
  }

  useEffect(() => {
    refreshContext().catch(() => setContext(null));
  }, [character.id]);

  return (
    <div className="chat-layout">
      <ChatWindow characterId={character.id} onAfterSend={() => refreshContext().catch(() => setContext(null))} />
      <CompanionPanel
        character={character}
        context={context}
        onMemoryChange={() => refreshContext().catch(() => setContext(null))}
      />
    </div>
  );
}
