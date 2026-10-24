import type {
  Character,
  CharacterAppearance,
  AppearanceSettings,
  AppearanceStage,
  ChatMessage,
  CompanionContext,
  Memory,
  UserProfile,
  VoiceOption,
  VoiceUploadConstraints,
} from "@ai-companion/shared";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type AccountUser = { id: string; email: string; display_name: string; created_at?: string };
export type AccountLimits = Record<"images_count" | "videos_count" | "text_messages_count" | "voice_messages_count", { used: number; limit: number }>;
export type MediaAsset = { id: string; character_id: string; media_type: string; url: string; prompt: string; created_at: string };
export type ExampleCharacter = {
  slug: string;
  name: string;
  age: number;
  gender: string;
  relationship_mode: string;
  visual_label: string;
  appearance_summary: string;
  personality_description: string;
  communication_style: string;
  biography: string;
  boundaries: string;
  likes: string;
  dislikes: string;
  appearance: AppearanceSettings;
  images: Record<"face" | "body" | "clothing", string>;
};

export class ApiError extends Error {
  constructor(message: string, public readonly status: number, public readonly code = "") {
    super(message);
  }
}

export function getApiAssetUrl(path: string) {
  if (!path || /^https?:\/\//i.test(path)) {
    return path;
  }
  return `${API_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    if (response.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new Event("ai-comp:unauthorized"));
    }
    let message = `API request failed: ${response.status}`;
    let code = "";
    try {
      const payload = await response.json();
      const detail = payload?.detail;
      if (typeof detail === "string") message = detail;
      else if (typeof detail?.message === "string") {
        message = detail.message;
        if (typeof detail.error === "string") code = detail.error;
      }
      else if (Array.isArray(detail)) {
        message = detail.map((item) => {
          const field = Array.isArray(item.loc) ? item.loc.filter((part: unknown) => part !== "body").join(".") : "";
          return `${field ? `${field}: ` : ""}${item.msg ?? "Invalid value"}`;
        }).join("; ");
      }
    } catch {
      // Keep the status-based message when the API does not return JSON.
    }
    throw new ApiError(publicErrorText(message), response.status, code);
  }

  return response.json() as Promise<T>;
}

export function getMe() { return request<AccountUser>("/auth/me"); }
export function registerAccount(email: string, password: string, display_name: string) {
  return request<AccountUser>("/auth/register", { method: "POST", body: JSON.stringify({ email, password, display_name }) });
}
export function loginAccount(email: string, password: string) {
  return request<AccountUser>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
}
export function logoutAccount() { return request<{ status: string }>("/auth/logout", { method: "POST" }); }
export function getAccountLimits() { return request<AccountLimits>("/limits"); }
export function listMedia(characterId: string) { return request<MediaAsset[]>(`/media/${characterId}`); }

export type CharacterCreateInput = {
  name: string;
  gender: string;
  relationship_mode: string;
  personality_description: string;
  communication_style: string;
  background_story: string;
  biography: string;
  boundaries: string;
  likes: string;
  dislikes: string;
  language: string;
  user_city: string;
  user_country: string;
  user_timezone: string;
  user_language: string;
  user_address_name: string;
  voice_id: string;
  response_length: Character["response_length"];
  warmth: number;
  initiative: number;
  playfulness: number;
  directness: number;
  emotionality: number;
  rationality: number;
};

export type CharacterUpdateInput = Pick<
  CharacterCreateInput,
  | "gender"
  | "relationship_mode"
  | "personality_description"
  | "communication_style"
  | "biography"
  | "boundaries"
  | "likes"
  | "dislikes"
  | "language"
  | "user_address_name"
  | "voice_id"
  | "response_length"
  | "warmth"
  | "initiative"
  | "playfulness"
  | "directness"
  | "emotionality"
  | "rationality"
>;

export function listVoiceOptions() {
  return request<VoiceOption[]>("/voice/catalog");
}

export function getVoiceUploadConstraints() {
  return request<VoiceUploadConstraints>("/voice/constraints");
}

export async function previewVoice(voiceId: string) {
  const response = await fetch(`${API_URL}/voice/preview`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ voice_id: voiceId }),
  });
  if (!response.ok) {
    let message = `Voice preview failed: ${response.status}`;
    try {
      const payload = await response.json();
      message = payload?.detail?.message ?? payload?.detail ?? message;
    } catch {
      // Keep the status-based message when the API does not return JSON.
    }
    throw new Error(message);
  }
  return response.blob();
}

export function listCharacters() {
  return request<Character[]>("/characters");
}

export function listExamples() {
  return request<ExampleCharacter[]>("/examples");
}

export function copyExample(slug: string) {
  return request<Character>(`/examples/${encodeURIComponent(slug)}/copy`, { method: "POST" });
}

export function createCharacter(input: CharacterCreateInput) {
  return request<Character>("/characters", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function generateBiographyVariants(input: Pick<CharacterCreateInput, "name" | "gender" | "personality_description" | "communication_style" | "biography" | "likes" | "dislikes">) {
  return request<{ variants: string[] }>("/characters/biography-variants", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getCharacter(characterId: string) {
  return request<Character>(`/characters/${characterId}`);
}

export function getAppearance(characterId: string) {
  return request<CharacterAppearance>(`/characters/${characterId}/appearance`);
}

export function selectAppearanceCandidate(characterId: string, stage: AppearanceStage, candidate_id: string, expected_revision: number) {
  return request<CharacterAppearance>(`/characters/${characterId}/appearance/select/${stage}`, {
    method: "POST", body: JSON.stringify({ expected_revision, candidate_id }),
  });
}

export function publishAppearance(characterId: string, expected_revision: number, confirm_gender_change: boolean) {
  return request<CharacterAppearance>(`/characters/${characterId}/appearance/publish`, {
    method: "POST", body: JSON.stringify({ expected_revision, confirm_gender_change }),
  });
}

export type AppearanceGenerationInput = {
  request_id: string;
  expected_revision: number;
  settings?: AppearanceSettings;
  count?: number;
  retry_of?: string;
  confirm_unknown_retry?: boolean;
};

export function generateAppearance(characterId: string, stage: AppearanceStage, input: AppearanceGenerationInput) {
  return request<CharacterAppearance>(`/characters/${characterId}/appearance/generate/${stage}`, {
    method: "POST", body: JSON.stringify(input),
  });
}

export function updateCharacter(characterId: string, input: CharacterUpdateInput) {
  return request<Character>(`/characters/${characterId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export type UserProfileUpdateInput = UserProfile & { character_id: string };

export function updateUserProfile(input: UserProfileUpdateInput) {
  return request<UserProfile>("/users/profile", {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function getChatHistory(characterId: string) {
  return request<ChatMessage[]>(`/chat/${characterId}`);
}

export function publicErrorText(value: string) {
  if (!/(?:venice|openrouter|wan[-\s]?2|seedance|qwen|grok|mistral|gemini|whisper|flux\.\d)/i.test(value)) return value;
  const status = value.match(/HTTP\s+\d{3}/i)?.[0];
  return `Не удалось завершить операцию${status ? ` (${status})` : ""}. Проверьте её статус перед повтором запроса.`;
}

export type ScenarioIdea = { title: string; opening_message: string };

export function generateScenarioIdeas(characterId: string) {
  return request<{ ideas: ScenarioIdea[]; source: "model" | "local" }>(`/chat/${characterId}/ideas`, { method: "POST" });
}

export type VideoMode = "animate_photo" | "reference_video";
export type VideoAspectRatio = "auto" | "16:9" | "9:16" | "4:3" | "3:4" | "1:1" | "2:3";
export type VideoQuote = {
  model: string;
  available: boolean;
  price_usd: string | null;
  unavailable_reason: string;
};
export type VideoJob = {
  id: string;
  mode: VideoMode;
  model: string;
  status: string;
  quote_usd: string;
  aspect_ratio: VideoAspectRatio;
  error: string;
  created_at: string;
};

export function videoPreset(_mode: VideoMode) {
  return { duration: "5s" as const, resolution: "480p" as const };
}

export function getVideoQuote(mode: VideoMode, aspectRatio: VideoAspectRatio = "auto") {
  return request<VideoQuote>("/video/quote", {
    method: "POST",
    body: JSON.stringify({ mode, ...videoPreset(mode), aspect_ratio: aspectRatio }),
  });
}

export function createVideo(characterId: string, input: {
  request_id: string;
  mode: VideoMode;
  prompt: string;
  aspect_ratio: VideoAspectRatio;
  source_message_id?: string;
  accepted_quote_usd: string;
}) {
  return request<VideoJob>(`/video/${characterId}`, {
    method: "POST",
    body: JSON.stringify({ ...input, ...videoPreset(input.mode) }),
  });
}

export function getVideoJob(characterId: string, jobId: string) {
  return request<VideoJob>(`/video/${characterId}/${jobId}`);
}

export function checkVideoJob(characterId: string, jobId: string) {
  return request<VideoJob>(`/video/${characterId}/${jobId}/check`, { method: "POST" });
}

export type VoiceChatResult = {
  message: ChatMessage;
  reply: string | null;
  character_state: CompanionContext["character_state"];
  error_type: string;
  error_message: string;
};

export async function uploadVoiceFile(
  characterId: string,
  audio: Blob,
  durationMs: number,
  uploadId: string,
) {
  const response = await fetch(`${API_URL}/voice/messages/${characterId}/upload`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": audio.type || "audio/webm",
      "X-Audio-Duration-Ms": String(Math.max(1, Math.round(durationMs))),
      "X-Voice-Upload-Id": uploadId,
    },
    body: audio,
  });

  if (!response.ok) {
    let message = `Voice upload failed: ${response.status}`;
    try {
      const payload = await response.json();
      message = payload?.detail?.message ?? payload?.detail ?? message;
    } catch {
      // Keep the status-based message when the API does not return JSON.
    }
    throw new Error(message);
  }

  return response.json() as Promise<ChatMessage>;
}

export function retryVoiceTranscription(messageId: string) {
  return request<VoiceChatResult>(`/voice/messages/${messageId}/transcribe`, {
    method: "POST",
  });
}

export function generateVoiceReply(messageId: string) {
  return request<VoiceChatResult>(`/voice/messages/${messageId}/reply`, {
    method: "POST",
  });
}

export function retryVoiceGeneration(messageId: string) {
  return request<ChatMessage>(`/voice/messages/${messageId}/retry-generation`, {
    method: "POST",
  });
}

export type ChatExportData = {
  schema_version: number;
  exported_at: string;
  character: Character;
  scene_context: CompanionContext["scene_context"];
  memories: Memory[];
  messages: ChatMessage[];
};

export function exportChat(characterId: string) {
  return request<ChatExportData>(`/chat/${characterId}/export`);
}

export function clearChatHistory(characterId: string) {
  return request<{
    status: string;
    character_id: string;
    deleted_messages: number;
    preserved_memories: number;
  }>(`/chat/${characterId}`, {
    method: "DELETE",
  });
}

export function deleteCharacter(characterId: string) {
  return request<{ status: string; character_id: string }>(`/characters/${characterId}`, {
    method: "DELETE",
  });
}

export function getCompanionContext(characterId: string) {
  return request<CompanionContext>(`/chat/${characterId}/context`);
}

export function sendChatMessage(characterId: string, message: string, requestId?: string) {
  return request<{
    reply: string;
    character_state: CompanionContext["character_state"];
    error_type: string;
    error_message: string;
  }>("/chat", {
    method: "POST",
      body: JSON.stringify({ character_id: characterId, message, request_id: requestId }),
  });
}

export function retryChatMessage(characterId: string) {
  return request<{
    reply: string;
    character_state: CompanionContext["character_state"];
    error_type: string;
    error_message: string;
  }>("/chat/retry", {
    method: "POST",
    body: JSON.stringify({ character_id: characterId }),
  });
}

export function createMemory(input: {
  character_id: string;
  memory_type: Memory["memory_type"];
  content: string;
  importance?: number;
}) {
  return request<Memory>("/memories", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function deleteMemory(memoryId: string) {
  return request<{ status: string }>(`/memories/${memoryId}`, {
    method: "DELETE",
  });
}

export function updateMemory(
  memoryId: string,
  input: {
    memory_type?: Memory["memory_type"];
    content?: string;
    importance?: number;
  },
) {
  return request<Memory>(`/memories/${memoryId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export type SceneUpdateInput = Pick<
  CompanionContext["scene_context"],
  | "character_id"
  | "presence_mode"
  | "location_name"
  | "location_description"
  | "time_description"
  | "user_position"
  | "character_position"
> & {
  start_new_scene?: boolean;
  previous_scene_summary?: string;
};

export function updateScene(input: SceneUpdateInput) {
  return request<CompanionContext["scene_context"]>("/scenes", {
    method: "PUT",
    body: JSON.stringify(input),
  });
}
