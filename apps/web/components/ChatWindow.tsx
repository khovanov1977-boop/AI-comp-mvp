"use client";

import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { ChatMessage } from "@ai-companion/shared";
import { getChatHistory, sendChatMessage } from "../lib/api";
import { MessageBubble } from "./MessageBubble";

export function ChatWindow({ characterId, onAfterSend }: { characterId: string; onAfterSend?: () => void }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement | null>(null);

  async function loadHistory() {
    const history = await getChatHistory(characterId);
    setMessages(history);
  }

  useEffect(() => {
    loadHistory().catch(() => setError("Could not load chat history."));
  }, [characterId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = draft.trim();
    if (!text) {
      return;
    }

    setDraft("");
    setIsSending(true);
    setError("");
    try {
      await sendChatMessage(characterId, text);
      await loadHistory();
      onAfterSend?.();
    } catch {
      setError("Could not send message. Check that the backend is running.");
    } finally {
      setIsSending(false);
    }
  }

  return (
    <section>
      <div className="chat-window">
        {messages.length === 0 ? <p className="muted">No messages yet.</p> : null}
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        <div ref={bottomRef} />
      </div>
      {error ? <p className="muted">{error}</p> : null}
      <form className="composer" onSubmit={submit}>
        <input
          className="input"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Write a message"
          disabled={isSending}
        />
        <button className="button" type="submit" disabled={isSending}>
          Send
        </button>
      </form>
    </section>
  );
}
