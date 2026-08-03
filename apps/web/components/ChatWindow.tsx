"use client";

import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { ChatMessage } from "@ai-companion/shared";
import { getChatHistory, retryChatMessage, sendChatMessage } from "../lib/api";
import { MessageBubble } from "./MessageBubble";

const MIN_REPLY_REVEAL_DELAY_MS = 700;
const MAX_REPLY_REVEAL_DELAY_MS = 4200;

function sleep(delayMs: number) {
  return new Promise((resolve) => window.setTimeout(resolve, delayMs));
}

function getReplyRevealDelay(reply: string) {
  const estimatedTypingMs = reply.length * 18;
  return Math.min(MAX_REPLY_REVEAL_DELAY_MS, Math.max(MIN_REPLY_REVEAL_DELAY_MS, estimatedTypingMs));
}

function getFriendlyErrorMessage(message: string) {
  if (message.includes("HTTP 429")) {
    return "The model is busy right now. Your message was saved; try again in a moment.";
  }
  if (message.toLowerCase().includes("timed out")) {
    return "The model took too long to answer. Your message was saved; try again.";
  }
  if (message.toLowerCase().includes("failed")) {
    return "The model connection failed. Your message was saved; try again.";
  }
  return message;
}

export function ChatWindow({ characterId, onAfterSend }: { characterId: string; onAfterSend?: () => void }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState("");
  const [canRetry, setCanRetry] = useState(false);
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
  }, [messages, isSending]);

  async function finishSuccessfulReply(reply: string) {
    await sleep(getReplyRevealDelay(reply));
    await loadHistory();
    onAfterSend?.();
    setCanRetry(false);
  }

  async function handleSendFailure(caughtError: unknown) {
    await loadHistory().catch(() => undefined);
    const message = caughtError instanceof Error ? caughtError.message : "Could not send message.";
    setError(getFriendlyErrorMessage(message));
    setCanRetry(true);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = draft.trim();
    if (!text) {
      return;
    }

    setDraft("");
    setIsSending(true);
    setError("");
    setCanRetry(false);
    try {
      const response = await sendChatMessage(characterId, text);
      await finishSuccessfulReply(response.reply);
    } catch (caughtError) {
      await handleSendFailure(caughtError);
    } finally {
      setIsSending(false);
    }
  }

  async function retryLastMessage() {
    setIsSending(true);
    setError("");
    setCanRetry(false);
    try {
      const response = await retryChatMessage(characterId);
      await finishSuccessfulReply(response.reply);
    } catch (caughtError) {
      await handleSendFailure(caughtError);
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
        {isSending ? <div className="typing-indicator">Typing...</div> : null}
        <div ref={bottomRef} />
      </div>
      {error ? (
        <div className="chat-error">
          <p>{error}</p>
          {canRetry ? (
            <button className="text-button" type="button" onClick={retryLastMessage} disabled={isSending}>
              Retry
            </button>
          ) : null}
        </div>
      ) : null}
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
