"use client";

import { useEffect, useState } from "react";
import type { Character, CompanionContext } from "@ai-companion/shared";
import { getCompanionContext } from "../lib/api";
import { ChatWindow } from "./ChatWindow";
import { CompanionPanel } from "./CompanionPanel";

export function ChatWorkspace({ character }: { character: Character }) {
  const [currentCharacter, setCurrentCharacter] = useState(character);
  const [context, setContext] = useState<CompanionContext | null>(null);
  const [contextError, setContextError] = useState("");

  async function refreshContext() {
    setContextError("");
    try {
      setContext(await getCompanionContext(currentCharacter.id));
    } catch (error) {
      setContext(null);
      setContextError(error instanceof Error ? error.message : "Could not load companion context.");
    }
  }

  useEffect(() => {
    setCurrentCharacter(character);
  }, [character]);

  useEffect(() => {
    refreshContext();
  }, [currentCharacter.id]);

  return (
    <div className="chat-layout">
      <ChatWindow characterId={currentCharacter.id} onAfterSend={() => refreshContext().catch(() => setContext(null))} />
      <CompanionPanel
        character={currentCharacter}
        context={context}
        contextError={contextError}
        onCharacterChange={setCurrentCharacter}
        onMemoryChange={() => refreshContext()}
      />
    </div>
  );
}
