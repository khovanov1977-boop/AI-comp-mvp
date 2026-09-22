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

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
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
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    let message = `API request failed: ${response.status}`;
    try {
      const payload = await response.json();
      const detail = payload?.detail;
      if (typeof detail === "string") message = detail;
      else if (typeof detail?.message === "string") message = detail.message;
      else if (Array.isArray(detail)) {
        message = detail.map((item) => {
          const field = Array.isArray(item.loc) ? item.loc.filter((part: unknown) => part !== "body").join(".") : "";
          return `${field ? `${field}: ` : ""}${item.msg ?? "Invalid value"}`;
        }).join("; ");
      }
    } catch {
      // Keep the status-based message when the API does not return JSON.
    }
    throw new ApiError(message, response.status);
  }

  return response.json() as Promise<T>;
}

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
  voice_id: string;
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
  | "voice_id"
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

export function createCharacter(input: CharacterCreateInput) {
  return request<Character>("/characters", {
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

export function sendChatMessage(characterId: string, message: string) {
  return request<{
    reply: string;
    character_state: CompanionContext["character_state"];
    error_type: string;
    error_message: string;
  }>("/chat", {
    method: "POST",
    body: JSON.stringify({ character_id: characterId, message }),
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
