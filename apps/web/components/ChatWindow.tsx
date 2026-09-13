"use client";

import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { ChatMessage, VoiceUploadConstraints } from "@ai-companion/shared";
import {
  generateVoiceReply,
  getChatHistory,
  getVoiceUploadConstraints,
  retryChatMessage,
  retryVoiceGeneration,
  retryVoiceTranscription,
  sendChatMessage,
  uploadVoiceFile,
} from "../lib/api";
import { MessageBubble } from "./MessageBubble";

const MIN_REPLY_REVEAL_DELAY_MS = 700;
const MAX_REPLY_REVEAL_DELAY_MS = 4200;
const DEFAULT_VOICE_CONSTRAINTS: VoiceUploadConstraints = {
  max_duration_ms: 120_000,
  max_file_size_bytes: 10 * 1024 * 1024,
  accepted_mime_types: ["audio/mp4", "audio/mpeg", "audio/ogg", "audio/wav", "audio/webm", "audio/x-wav"],
};

type VoicePhase = "idle" | "requesting_microphone" | "uploading" | "transcribing" | "generating";

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

function formatFileSize(bytes: number) {
  return `${Math.round(bytes / (1024 * 1024))} MB`;
}

function createUploadId() {
  if (typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function normalizeMimeType(value: string) {
  return value.split(";", 1)[0].trim().toLowerCase();
}

function getSupportedAudioMimeType(acceptedMimeTypes: string[]) {
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];
  const accepted = new Set(acceptedMimeTypes.map(normalizeMimeType));
  return (
    candidates.find(
      (candidate) => accepted.has(normalizeMimeType(candidate)) && MediaRecorder.isTypeSupported(candidate),
    ) ?? ""
  );
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
  const [voicePhase, setVoicePhase] = useState<VoicePhase>("idle");
  const [voiceConstraints, setVoiceConstraints] = useState(DEFAULT_VOICE_CONSTRAINTS);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [pendingVoice, setPendingVoice] = useState<{
    audio: Blob;
    durationMs: number;
    uploadId: string;
  } | null>(null);
  const [voiceUploadFailed, setVoiceUploadFailed] = useState(false);
  const [retryingVoiceMessageId, setRetryingVoiceMessageId] = useState<string | null>(null);
  const [retryingVoiceGenerationMessageId, setRetryingVoiceGenerationMessageId] = useState<string | null>(null);
  const [retryVoiceReplyMessageId, setRetryVoiceReplyMessageId] = useState<string | null>(null);
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
    getVoiceUploadConstraints().then(setVoiceConstraints).catch(() => undefined);
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
  }, [messages, isSending, voicePhase]);

  const isProcessingVoice = voicePhase !== "idle" && voicePhase !== "requesting_microphone";
  const voicePhaseLabel = {
    idle: "",
    requesting_microphone: "Requesting microphone access...",
    uploading: "Uploading voice message...",
    transcribing: "Transcribing voice message...",
    generating: "Generating character reply and voice...",
  }[voicePhase];

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
    setRetryVoiceReplyMessageId(null);
    try {
      const response = await sendChatMessage(characterId, text);
      await finishSuccessfulReply(response.reply);
      if (response.error_message) {
        setError(response.error_message);
        setCanRetry(response.error_type.startsWith("llm_") || response.error_type === "chat_error");
      }
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
    setRetryVoiceReplyMessageId(null);
    try {
      const response = await retryChatMessage(characterId);
      await finishSuccessfulReply(response.reply);
      if (response.error_message) {
        setError(response.error_message);
        setCanRetry(response.error_type.startsWith("llm_") || response.error_type === "chat_error");
      }
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
    setVoicePhase("idle");
  }

  function finishRecordedVoice(recorder: MediaRecorder) {
    const durationMs = Math.min(
      voiceConstraints.max_duration_ms,
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
    if (audio.size > voiceConstraints.max_file_size_bytes) {
      setError(
        `This recording is larger than ${formatFileSize(voiceConstraints.max_file_size_bytes)}. ` +
          "Record a shorter voice message.",
      );
      return;
    }
    if (!voiceConstraints.accepted_mime_types.map(normalizeMimeType).includes(normalizeMimeType(audio.type))) {
      setError("This browser produced an audio format that the server cannot process.");
      return;
    }
    setVoiceUploadFailed(false);
    setPendingVoice({ audio, durationMs, uploadId: createUploadId() });
  }

  async function startVoiceRecording() {
    if (isSending || voicePhase !== "idle" || isRecording || pendingVoice) {
      return;
    }
    setError("");
    setCanRetry(false);
    setRetryVoiceReplyMessageId(null);

    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("Voice recording is not supported in this browser.");
      return;
    }

    try {
      const mimeType = getSupportedAudioMimeType(voiceConstraints.accepted_mime_types);
      if (!mimeType) {
        setError("This browser cannot record a supported audio format.");
        return;
      }
      setVoicePhase("requesting_microphone");
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType });
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
      setVoicePhase("idle");
      setIsRecording(true);
      setRecordingSeconds(0);
      recordingIntervalRef.current = window.setInterval(() => {
        setRecordingSeconds(Math.floor((Date.now() - recordingStartedAtRef.current) / 1000));
      }, 250);
      recordingTimeoutRef.current = window.setTimeout(() => {
        if (recorder.state === "recording") {
          recorder.stop();
        }
      }, voiceConstraints.max_duration_ms);
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
    if (!pendingVoice || isProcessingVoice) {
      return;
    }
    setError("");
    setCanRetry(false);
    setRetryVoiceReplyMessageId(null);
    let activePhase: VoicePhase = "uploading";
    let uploadedMessageId = "";
    try {
      setVoicePhase("uploading");
      const uploadedMessage = await uploadVoiceFile(
        characterId,
        pendingVoice.audio,
        pendingVoice.durationMs,
        pendingVoice.uploadId,
      );
      uploadedMessageId = uploadedMessage.id;
      setPendingVoice(null);
      setVoiceUploadFailed(false);
      await loadHistory();

      if (uploadedMessage.transcription_status !== "completed") {
        activePhase = "transcribing";
        setVoicePhase("transcribing");
        const transcription = await retryVoiceTranscription(uploadedMessage.id);
        await loadHistory();
        if (transcription.error_message) {
          setError(transcription.error_message);
          return;
        }
      }

      activePhase = "generating";
      setVoicePhase("generating");
      const response = await generateVoiceReply(uploadedMessage.id);
      if (response.reply) {
        await sleep(getReplyRevealDelay(response.reply));
      }
      await loadHistory();
      onAfterSend?.();
      if (response.error_message) {
        setError(response.error_message);
        if (response.error_type.startsWith("llm_") || response.error_type === "chat_error") {
          setRetryVoiceReplyMessageId(uploadedMessage.id);
        }
      }
    } catch (caughtError) {
      const message = caughtError instanceof Error ? caughtError.message : "Could not send voice message.";
      await loadHistory().catch(() => undefined);
      if (activePhase === "uploading") {
        setVoiceUploadFailed(true);
        setError(`${message} The recording is still available; retry when ready.`);
      } else if (activePhase === "transcribing") {
        setError(`${message} Retry transcription from the saved voice message.`);
      } else {
        setRetryVoiceReplyMessageId(uploadedMessageId || null);
        setError(`${message} The recording and transcript were saved; retry the reply.`);
      }
    } finally {
      setVoicePhase("idle");
    }
  }

  async function finishVoiceReply(messageId: string) {
    setVoicePhase("generating");
    setRetryVoiceReplyMessageId(null);
    const response = await generateVoiceReply(messageId);
    if (response.reply) {
      await sleep(getReplyRevealDelay(response.reply));
    }
    await loadHistory();
    onAfterSend?.();
    if (response.error_message) {
      setError(response.error_message);
      if (response.error_type.startsWith("llm_") || response.error_type === "chat_error") {
        setRetryVoiceReplyMessageId(messageId);
      }
    }
  }

  async function retryVoiceReply(messageId: string) {
    setError("");
    try {
      await finishVoiceReply(messageId);
    } catch (caughtError) {
      const message = caughtError instanceof Error ? caughtError.message : "Could not retry the reply.";
      setError(message);
      setRetryVoiceReplyMessageId(messageId);
      await loadHistory().catch(() => undefined);
    } finally {
      setVoicePhase("idle");
    }
  }

  async function retryVoiceMessage(messageId: string) {
    if (retryingVoiceMessageId) {
      return;
    }
    setRetryingVoiceMessageId(messageId);
    setVoicePhase("transcribing");
    setError("");
    setCanRetry(false);
    try {
      const response = await retryVoiceTranscription(messageId);
      await loadHistory();
      if (response.error_message) {
        setError(response.error_message);
        return;
      }
      await finishVoiceReply(messageId);
    } catch (caughtError) {
      const message = caughtError instanceof Error ? caughtError.message : "Could not retry transcription.";
      setError(message);
      await loadHistory().catch(() => undefined);
    } finally {
      setRetryingVoiceMessageId(null);
      setVoicePhase("idle");
    }
  }

  async function retryGeneratedVoice(messageId: string) {
    if (retryingVoiceGenerationMessageId || isProcessingVoice) {
      return;
    }
    setRetryingVoiceGenerationMessageId(messageId);
    setVoicePhase("generating");
    setError("");
    try {
      await retryVoiceGeneration(messageId);
      await loadHistory();
      onAfterSend?.();
    } catch (caughtError) {
      const message = caughtError instanceof Error ? caughtError.message : "Could not retry voice generation.";
      setError(message);
      await loadHistory().catch(() => undefined);
    } finally {
      setRetryingVoiceGenerationMessageId(null);
      setVoicePhase("idle");
    }
  }

  function discardPendingVoice() {
    if (!isProcessingVoice) {
      setPendingVoice(null);
      setVoiceUploadFailed(false);
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
            retryingVoiceGenerationMessageId={retryingVoiceGenerationMessageId}
            canRetryVoiceReply={
              message.role === "user" &&
              message.message_type === "voice" &&
              message.transcription_status === "completed" &&
              messages.at(-1)?.id === message.id
            }
            isVoiceReplyBusy={isProcessingVoice}
            onRetryVoice={retryVoiceMessage}
            onRetryVoiceReply={retryVoiceReply}
            onRetryVoiceGeneration={retryGeneratedVoice}
          />
        ))}
        {isSending ? <div className="typing-indicator">Typing...</div> : null}
        {voicePhaseLabel ? (
          <div className="typing-indicator voice-processing-indicator" role="status" aria-live="polite">
            {voicePhaseLabel}
          </div>
        ) : null}
        <div ref={bottomRef} />
      </div>
      {error ? (
        <div className="chat-error">
          <p>{error}</p>
          {retryVoiceReplyMessageId ? (
            <button
              className="text-button"
              type="button"
              onClick={() => retryVoiceReply(retryVoiceReplyMessageId)}
              disabled={isProcessingVoice}
            >
              Retry reply
            </button>
          ) : canRetry ? (
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
          <small className="voice-limit-hint">
            Maximum {formatRecordingTime(Math.floor(voiceConstraints.max_duration_ms / 1000))} ·{" "}
            {formatFileSize(voiceConstraints.max_file_size_bytes)}
          </small>
          <button
            className="secondary-button"
            type="button"
            disabled={isProcessingVoice}
            onClick={discardPendingVoice}
          >
            Cancel
          </button>
          <button className="button" type="button" disabled={isProcessingVoice} onClick={sendPendingVoice}>
            {voiceUploadFailed ? "Retry upload" : "Send voice"}
          </button>
        </div>
      ) : (
        <form className="composer" onSubmit={submit}>
          <input
            className="input"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Write a message"
            disabled={isSending || isProcessingVoice || voicePhase === "requesting_microphone"}
          />
          <button
            className="secondary-button voice-button"
            type="button"
            disabled={isSending || isProcessingVoice || voicePhase === "requesting_microphone"}
            onClick={startVoiceRecording}
          >
            Voice
          </button>
          <button
            className="button"
            type="submit"
            disabled={isSending || isProcessingVoice || voicePhase === "requesting_microphone"}
          >
            Send
          </button>
        </form>
      )}
    </section>
  );
}
