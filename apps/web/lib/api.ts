import type { Character, ChatMessage, CompanionContext, Memory, UserProfile } from "@ai-companion/shared";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
      message = payload?.detail?.message ?? payload?.detail ?? message;
    } catch {
      // Keep the status-based message when the API does not return JSON.
    }
    throw new Error(message);
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
  warmth: number;
  initiative: number;
  playfulness: number;
  directness: number;
  emotionality: number;
  rationality: number;
};

export type CharacterUpdateInput = Pick<
  CharacterCreateInput,
  | "relationship_mode"
  | "personality_description"
  | "communication_style"
  | "warmth"
  | "initiative"
  | "playfulness"
  | "directness"
  | "emotionality"
  | "rationality"
>;

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

export async function uploadVoiceMessage(characterId: string, audio: Blob, durationMs: number) {
  const response = await fetch(`${API_URL}/voice/messages/${characterId}`, {
    method: "POST",
    headers: {
      "Content-Type": audio.type || "audio/webm",
      "X-Audio-Duration-Ms": String(Math.max(1, Math.round(durationMs))),
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
  return request<{ reply: string; character_state: CompanionContext["character_state"] }>("/chat", {
    method: "POST",
    body: JSON.stringify({ character_id: characterId, message }),
  });
}

export function retryChatMessage(characterId: string) {
  return request<{ reply: string; character_state: CompanionContext["character_state"] }>("/chat/retry", {
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
