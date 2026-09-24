export type AppearanceStage = "face" | "body" | "clothing";

export type AppearanceSettings = {
  gender: "female" | "male" | "non_binary";
  style?: "photo" | "cartoon" | "anime" | "3d" | "digital_painting" | "comic" | "watercolor";
  appearance_type?: "european" | "african" | "asian" | "arab" | "latin_american" | "caucasus";
  age?: number;
  hair_color?: string;
  eye_color?: string;
  hairstyle?: string;
  glasses?: boolean;
  face_details?: string;
  body_type?: "ordinary" | "fit" | "athletic" | "full" | "fat";
  face_adjustment?: "allow" | "preserve";
  body_details?: string;
  clothing?: string;
  clothing_details?: string;
};

export type AppearanceCounts = Record<AppearanceStage, number>;

export type ImageGenerationJob = {
  id: string;
  stage: AppearanceStage;
  model: string;
  status: "queued" | "running" | "completed" | "partial" | "failed" | "interrupted";
  retry_of: string | null;
  created_at: string;
  outputs: Array<{
    index: number;
    status: "queued" | "running" | "completed" | "failed" | "unknown" | "not_started";
    candidate_id: string | null;
    cost_usd: string | null;
    error: string;
  }>;
};

export type CharacterAppearance = {
  character_id: string;
  revision: number;
  settings: Partial<AppearanceSettings>;
  counts: AppearanceCounts;
  selections: Partial<Record<AppearanceStage, string>>;
  candidates: Array<{ id: string; stage: AppearanceStage; url: string; current: boolean }>;
  published: null | {
    version: number;
    settings: AppearanceSettings;
    references: Partial<Record<AppearanceStage, { candidate_id: string; asset_id: string; url: string }>>;
  };
  generation_available: boolean;
  generation_unavailable_reason: string;
  image_model: string;
  image_edit_model: string;
  image_provider: string;
  jobs: ImageGenerationJob[];
};

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
  voice_id: string;
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
  created_at: string;
};

export type VoiceOption = {
  id: string;
  gender: "female" | "male";
  age_group: string;
  description: string;
};

export type VoiceUploadConstraints = {
  max_duration_ms: number;
  max_file_size_bytes: number;
  accepted_mime_types: string[];
};

export type ChatMessage = {
  id: string;
  character_id: string;
  role: "user" | "assistant";
  content: string;
  message_type: "text" | "voice" | "image" | "video";
  audio_url: string;
  audio_mime_type: string;
  audio_duration_ms: number | null;
  transcription_status: "not_applicable" | "pending" | "completed" | "failed";
  transcription_error: string;
  voice_generation_status: "not_applicable" | "pending" | "completed" | "failed";
  voice_generation_error: string;
  voice_generation_can_retry: boolean;
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
    formal_name: string;
    preferred_name: string;
    casual_name: string;
    vocative_name: string;
    age: number | null;
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
    time_description: string;
    user_position: string;
    character_position: string;
    context_started_at: string | null;
  };
  memory_meta: {
    total_count: number;
    visible_count: number;
    visible_limit: number;
    counts_by_category: Record<string, number>;
    extraction_mode: "rule_based" | string;
    note: string;
  };
  memories: Memory[];
};

export type UserProfile = CompanionContext["user_context"];
