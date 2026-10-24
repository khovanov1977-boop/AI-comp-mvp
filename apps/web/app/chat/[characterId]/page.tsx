"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import type { Character } from "@ai-companion/shared";
import { ChatWorkspace } from "../../../components/ChatWorkspace";
import { RequireAuth } from "../../../components/AppChrome";
import { useAuth } from "../../../components/AuthProvider";
import { getCharacter } from "../../../lib/api";

export default function ChatPage() {
  const { characterId } = useParams<{ characterId: string }>();
  const { user } = useAuth();
  const [character, setCharacter] = useState<Character | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { if (user && characterId) getCharacter(characterId).then(setCharacter).catch((cause) => setError(cause instanceof Error ? cause.message : "Чат не найден.")); }, [user, characterId]);
  return <RequireAuth><main className="shell chat-page">
    <div className="chat-page-heading"><Link className="back-link" href="/characters">← Все персонажи</Link>{character && <><div className="chat-heading-avatar">{character.name.slice(0, 1).toUpperCase()}</div><div><span className="eyebrow">ВАШ ЛИЧНЫЙ ДИАЛОГ</span><h1>{character.name}</h1><p>{character.communication_style === "natural and conversational" ? "Естественный, непринуждённый" : character.communication_style || "Всегда рядом для разговора"}</p></div></>}</div>
    {error && <p className="form-error" role="alert">{error}</p>}
    {character ? <ChatWorkspace character={character} /> : !error ? <div className="page-loading"><span className="loading-orb" />Открываем диалог…</div> : null}
  </main></RequireAuth>;
}
