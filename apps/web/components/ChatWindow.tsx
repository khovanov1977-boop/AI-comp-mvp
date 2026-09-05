"use client";

import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { ChatMessage } from "@ai-companion/shared";
import {
  getChatHistory,
  retryChatMessage,
  retryVoiceTranscription,
  sendChatMessage,
  uploadVoiceMessage,
} from "../lib/api";
import { MessageBubble } from "./MessageBubble";

const MIN_REPLY_REVEAL_DELAY_MS = 700;
const MAX_REPLY_REVEAL_DELAY_MS = 4200;
const MAX_VOICE_DURATION_MS = 120_000;

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

function formatRecordingTime(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
}

function getSupportedAudioMimeType() {
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];
  return candidates.find((candidate) => MediaRecorder.isTypeSupported(candidate)) ?? "";
}

export function ChatWindow({
  characterId,
  historyRevision = 0,
  onAfterSend,
}: {
  characterId: string;
  historyRevision?: number;
  onAfterSend?: () => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isUploadingVoice, setIsUploadingVoice] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [pendingVoice, setPendingVoice] = useState<{ audio: Blob; durationMs: number } | null>(null);
  const [retryingVoiceMessageId, setRetryingVoiceMessageId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [canRetry, setCanRetry] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const voiceChunksRef = useRef<Blob[]>([]);
  const recordingStartedAtRef = useRef(0);
  const cancelRecordingRef = useRef(false);
  const recordingIntervalRef = useRef<number | null>(null);
  const recordingTimeoutRef = useRef<number | null>(null);

  async function loadHistory() {
    const history = await getChatHistory(characterId);
    setMessages(history);
  }

  useEffect(() => {
    setError("");
    setCanRetry(false);
    loadHistory().catch(() => setError("Could not load chat history."));
  }, [characterId, historyRevision]);

  useEffect(() => {
    return () => {
      cancelRecordingRef.current = true;
      if (mediaRecorderRef.current?.state === "recording") {
        mediaRecorderRef.current.stop();
      }
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
      if (recordingIntervalRef.current !== null) {
        window.clearInterval(recordingIntervalRef.current);
      }
      if (recordingTimeoutRef.current !== null) {
        window.clearTimeout(recordingTimeoutRef.current);
      }
    };
  }, []);

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

  function clearRecordingResources() {
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    mediaStreamRef.current = null;
    mediaRecorderRef.current = null;
    if (recordingIntervalRef.current !== null) {
      window.clearInterval(recordingIntervalRef.current);
      recordingIntervalRef.current = null;
    }
    if (recordingTimeoutRef.current !== null) {
      window.clearTimeout(recordingTimeoutRef.current);
      recordingTimeoutRef.current = null;
    }
    setIsRecording(false);
    setRecordingSeconds(0);
  }

  function finishRecordedVoice(recorder: MediaRecorder) {
    const durationMs = Math.min(
      MAX_VOICE_DURATION_MS,
      Math.max(1, Date.now() - recordingStartedAtRef.current),
    );
    const chunks = voiceChunksRef.current;
    voiceChunksRef.current = [];
    const wasCancelled = cancelRecordingRef.current;
    clearRecordingResources();

    if (wasCancelled) {
      return;
    }

    const audio = new Blob(chunks, {
      type: recorder.mimeType || chunks[0]?.type || "audio/webm",
    });
    if (audio.size === 0) {
      setError("The microphone did not produce an audio recording.");
      return;
    }
    setPendingVoice({ audio, durationMs });
  }

  async function startVoiceRecording() {
    if (isSending || isUploadingVoice || isRecording || pendingVoice) {
      return;
    }
    setError("");
    setCanRetry(false);

    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("Voice recording is not supported in this browser.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = getSupportedAudioMimeType();
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      mediaStreamRef.current = stream;
      mediaRecorderRef.current = recorder;
      voiceChunksRef.current = [];
      cancelRecordingRef.current = false;
      recordingStartedAtRef.current = Date.now();

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          voiceChunksRef.current.push(event.data);
        }
      };
      recorder.onstop = () => {
        finishRecordedVoice(recorder);
      };
      recorder.onerror = () => {
        cancelRecordingRef.current = true;
        setError("The microphone recording failed.");
        if (recorder.state !== "inactive") {
          recorder.stop();
        } else {
          clearRecordingResources();
        }
      };

      recorder.start();
      setIsRecording(true);
      setRecordingSeconds(0);
      recordingIntervalRef.current = window.setInterval(() => {
        setRecordingSeconds(Math.floor((Date.now() - recordingStartedAtRef.current) / 1000));
      }, 250);
      recordingTimeoutRef.current = window.setTimeout(() => {
        if (recorder.state === "recording") {
          recorder.stop();
        }
      }, MAX_VOICE_DURATION_MS);
    } catch (caughtError) {
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
      clearRecordingResources();
      const isPermissionError = caughtError instanceof DOMException && caughtError.name === "NotAllowedError";
      setError(
        isPermissionError
          ? "Microphone access was denied. Allow microphone access in the browser and try again."
          : "Could not start microphone recording.",
      );
    }
  }

  function stopVoiceRecording() {
    cancelRecordingRef.current = false;
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.stop();
    }
  }

  function cancelVoiceRecording() {
    cancelRecordingRef.current = true;
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.stop();
    } else {
      voiceChunksRef.current = [];
      clearRecordingResources();
    }
  }

  async function sendPendingVoice() {
    if (!pendingVoice || isUploadingVoice) {
      return;
    }
    setIsUploadingVoice(true);
    setError("");
    try {
      const response = await uploadVoiceMessage(characterId, pendingVoice.audio, pendingVoice.durationMs);
      setPendingVoice(null);
      if (response.reply) {
        await sleep(getReplyRevealDelay(response.reply));
      }
      await loadHistory();
      onAfterSend?.();
      if (response.error_message) {
        setError(response.error_message);
        setCanRetry(response.error_type.startsWith("llm_") || response.error_type === "chat_error");
      }
    } catch (caughtError) {
      const message = caughtError instanceof Error ? caughtError.message : "Could not send voice message.";
      setError(message);
    } finally {
      setIsUploadingVoice(false);
    }
  }

  async function retryVoiceMessage(messageId: string) {
    if (retryingVoiceMessageId) {
      return;
    }
    setRetryingVoiceMessageId(messageId);
    setError("");
    setCanRetry(false);
    try {
      const response = await retryVoiceTranscription(messageId);
      if (response.reply) {
        await sleep(getReplyRevealDelay(response.reply));
      }
      await loadHistory();
      onAfterSend?.();
      if (response.error_message) {
        setError(response.error_message);
        setCanRetry(response.error_type.startsWith("llm_") || response.error_type === "chat_error");
      }
    } catch (caughtError) {
      const message = caughtError instanceof Error ? caughtError.message : "Could not retry transcription.";
      setError(message);
      await loadHistory().catch(() => undefined);
    } finally {
      setRetryingVoiceMessageId(null);
    }
  }

  function discardPendingVoice() {
    if (!isUploadingVoice) {
      setPendingVoice(null);
      setError("");
    }
  }

  return (
    <section>
      <div className="chat-window">
        {messages.length === 0 ? <p className="muted">No messages yet.</p> : null}
        {messages.map((message) => (
          <MessageBubble
            key={message.id}
            message={message}
            retryingVoiceMessageId={retryingVoiceMessageId}
            onRetryVoice={retryVoiceMessage}
          />
        ))}
        {isSending ? <div className="typing-indicator">Typing...</div> : null}
        {isUploadingVoice ? <div className="typing-indicator">Processing voice message...</div> : null}
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
      {isRecording ? (
        <div className="voice-recorder" role="status" aria-live="polite">
          <span className="recording-dot" aria-hidden="true" />
          <strong>Recording {formatRecordingTime(recordingSeconds)}</strong>
          <button className="secondary-button" type="button" onClick={cancelVoiceRecording}>
            Cancel
          </button>
          <button className="button" type="button" onClick={stopVoiceRecording}>
            Stop
          </button>
        </div>
      ) : pendingVoice ? (
        <div className="voice-recorder" role="status" aria-live="polite">
          <strong>
            Voice message ready · {formatRecordingTime(Math.max(1, Math.round(pendingVoice.durationMs / 1000)))}
          </strong>
          <button
            className="secondary-button"
            type="button"
            disabled={isUploadingVoice}
            onClick={discardPendingVoice}
          >
            Cancel
          </button>
          <button className="button" type="button" disabled={isUploadingVoice} onClick={sendPendingVoice}>
            {isUploadingVoice ? "Sending..." : "Send voice"}
          </button>
        </div>
      ) : (
        <form className="composer" onSubmit={submit}>
          <input
            className="input"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Write a message"
            disabled={isSending || isUploadingVoice}
          />
          <button
            className="secondary-button voice-button"
            type="button"
            disabled={isSending || isUploadingVoice}
            onClick={startVoiceRecording}
          >
            Voice
          </button>
          <button className="button" type="submit" disabled={isSending || isUploadingVoice}>
            Send
          </button>
        </form>
      )}
    </section>
  );
}
