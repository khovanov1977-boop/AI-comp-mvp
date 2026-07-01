import type { Character, ChatMessage, CompanionContext, Memory } from "@ai-companion/shared";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
    throw new Error(`API request failed: ${response.status}`);
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
  user_nickname: string;
};

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

export function getChatHistory(characterId: string) {
  return request<ChatMessage[]>(`/chat/${characterId}`);
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
