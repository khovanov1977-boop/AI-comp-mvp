export type Character = {
  id: string;
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
  user_city: string;
  user_country: string;
  user_timezone: string;
  user_language: string;
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

export type CharacterState = {
  mood: string;
  trust_level: number;
  attachment_level: number;
  energy_level: number;
};

export type Memory = {
  id: string;
  character_id: string;
  memory_type: "user_fact" | "preference" | "life_event" | "relationship_note" | "system_note";
  content: string;
  importance: number;
  created_at: string;
};

export type CompanionContext = {
  character_state: CharacterState;
  user_context: {
    display_name: string;
    city: string;
    country: string;
    timezone: string;
    language: string;
  };
  scene_context: {
    character_id: string;
    presence_mode: "remote_chat" | "same_place" | "virtual_roleplay";
    location_name: string;
    location_description: string;
    user_position: string;
    character_position: string;
  };
  memories: Memory[];
};
