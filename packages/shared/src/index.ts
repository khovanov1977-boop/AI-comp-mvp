export type Character = {
  id: string;
  name: string;
  gender: string;
  relationship_mode: string;
  personality_description: string;
  communication_style: string;
  background_story: string;
  boundaries: string;
  created_at: string;
};

export type ChatMessage = {
  id: string;
  character_id: string;
  role: "user" | "assistant";
  content: string;
  message_type: "text" | "voice" | "image" | "video";
  created_at: string;
};
