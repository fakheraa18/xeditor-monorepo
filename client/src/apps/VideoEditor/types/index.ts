/**
 * Video Editor TypeScript Types
 *
 * These types mirror the Pydantic models on the server.
 * Single source of truth for client-side type definitions.
 */

// ─────────────────────────────────────────────────────────────────────────────
// Enums
// ─────────────────────────────────────────────────────────────────────────────

export type Orientation = 'landscape' | 'portrait' | 'square';

export type ClipSourceType =
  | 'generated_video'
  | 'generated_image'
  | 'imported'
  | 'placeholder'
  | 'audio';

export type ClipStatus = 'draft' | 'keyframe_ready' | 'queued' | 'generating' | 'done' | 'error';

export type GenerationMode = 'prompt_only' | 'i2v' | 'flf' | 't2v';

export type JobStatus = 'pending' | 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

export type JobType =
  | 'story_generate'
  | 'tts_generate'
  | 'image_generate'
  | 'video_generate'
  | 'music_generate'
  | 'final_merge';

export type RegenerationMode =
  | 'preview_audio'
  | 'regen_audio'
  | 'regen_video'
  | 'regen_audio_video'
  | 'regen_chain'
  | 'regen_all_stale';

export type GeneratorType = 'llm' | 'tts' | 't2i' | 'i2v' | 't2v' | 'music' | 'upscaler';

// ─────────────────────────────────────────────────────────────────────────────
// Canvas / Project Settings
// ─────────────────────────────────────────────────────────────────────────────

export interface CanvasPreset {
  name: string;
  width: number;
  height: number;
  fps: number;
  orientation: Orientation;
}

export const CANVAS_PRESETS: Record<string, CanvasPreset> = {
  '1080p_landscape': {
    name: '1080p Landscape',
    width: 1920,
    height: 1080,
    fps: 30,
    orientation: 'landscape',
  },
  '1080p_portrait': {
    name: '1080p Portrait',
    width: 1080,
    height: 1920,
    fps: 30,
    orientation: 'portrait',
  },
  '720p_landscape': {
    name: '720p Landscape',
    width: 1280,
    height: 720,
    fps: 30,
    orientation: 'landscape',
  },
  '720p_portrait': {
    name: '720p Portrait',
    width: 720,
    height: 1280,
    fps: 30,
    orientation: 'portrait',
  },
  '4k_landscape': {
    name: '4K Landscape',
    width: 3840,
    height: 2160,
    fps: 30,
    orientation: 'landscape',
  },
  square_1080: {
    name: 'Square 1080',
    width: 1080,
    height: 1080,
    fps: 30,
    orientation: 'square',
  },
  youtube_shorts: {
    name: 'YouTube Shorts',
    width: 1080,
    height: 1920,
    fps: 30,
    orientation: 'portrait',
  },
  tiktok: {
    name: 'TikTok',
    width: 1080,
    height: 1920,
    fps: 30,
    orientation: 'portrait',
  },
  instagram_reel: {
    name: 'Instagram Reel',
    width: 1080,
    height: 1920,
    fps: 30,
    orientation: 'portrait',
  },
};

export interface CanvasSettings {
  preset?: string;
  width: number;
  height: number;
  fps: number;
  orientation: Orientation;
}

export interface DefaultGeneratorSelections {
  story_llm?: string;
  tts?: string;
  t2i?: string;
  i2v?: string;
  t2v?: string;
  music?: string;
  upscaler?: string;
}

export interface ProjectSettings {
  vram_target_gb: number;
  canvas: CanvasSettings;
  default_generators: DefaultGeneratorSelections;
}

// ─────────────────────────────────────────────────────────────────────────────
// Asset Library
// ─────────────────────────────────────────────────────────────────────────────

export interface AssetRef {
  asset_id: string;
  asset_type: string;
}

export interface CharacterAsset {
  id: string;
  name: string;
  code: string;
  description?: string;
  image_path?: string;
  voice_sample_path?: string;
  lora_path?: string;
  style_hints?: string;
  created_at: number;
  updated_at: number;
}

export interface PropAsset {
  id: string;
  name: string;
  code: string;
  description?: string;
  image_path?: string;
  category?: string;
  created_at: number;
  updated_at: number;
}

export interface VoiceAsset {
  id: string;
  name: string;
  code: string;
  sample_path: string;
  description?: string;
  language: string;
  gender?: string;
  created_at: number;
  updated_at: number;
}

export interface GeneratedAsset {
  id: string;
  asset_type: string;
  path: string;
  source_prompt?: string;
  generator_id?: string;
  generator_config?: Record<string, unknown>;
  width?: number;
  height?: number;
  duration_seconds?: number;
  created_at: number;
}

export interface AssetLibrary {
  characters: CharacterAsset[];
  props: PropAsset[];
  voices: VoiceAsset[];
  generated: GeneratedAsset[];
}

// ─────────────────────────────────────────────────────────────────────────────
// Story / Script
// ─────────────────────────────────────────────────────────────────────────────

export interface ScriptLine {
  character_id?: string;
  text: string;
  emotion_hint?: string;
  voice_override?: string;
  duration_hint?: number;
}

export interface ClipScript {
  lines: ScriptLine[];
}

export interface SceneDescription {
  visual_prompt: string;
  negative_prompt?: string;
  motion_prompt?: string;
  camera_notes?: string;
  style_ref?: AssetRef;
}

export interface StoryScene {
  id: string;
  title?: string;
  order: number;
  script: ClipScript;
  description: SceneDescription;
  character_ids: string[];
  prop_ids: string[];
  duration_estimate?: number;
  notes?: string;
}

export interface Story {
  title?: string;
  genre?: string;
  synopsis?: string;
  scenes: StoryScene[];
  created_at: number;
  updated_at: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Timeline / Clips
// ─────────────────────────────────────────────────────────────────────────────

export interface ClipRef {
  clip_id: string;
  frame: string;
}

export interface GenerationSpec {
  mode: GenerationMode;
  prompt?: string;
  negative_prompt?: string;
  motion_prompt?: string;
  first_frame?: AssetRef;
  last_frame?: AssetRef;
  link_first_frame_from?: ClipRef;
  link_last_frame_to?: ClipRef;
  style_ref?: AssetRef;
  character_refs: AssetRef[];
  generator_id?: string;
  generator_config?: Record<string, unknown>;
}

export interface TimelineClip {
  id: string;
  track_id: string;
  start_time: number;
  duration: number;
  source_type: ClipSourceType;
  scene_id?: string;
  generation_spec?: GenerationSpec;
  script?: ClipScript;
  status: ClipStatus;
  keyframe_path?: string;
  artifact_path?: string;
  preview_path?: string;
  script_edited_at?: number;
  keyframe_edited_at?: number;
  style_edited_at?: number;
  audio_generated_at?: number;
  video_generated_at?: number;
}

export interface TimelineTrack {
  id: string;
  name: string;
  type: string;
  order: number;
  muted: boolean;
  locked: boolean;
}

export interface Timeline {
  tracks: TimelineTrack[];
  clips: TimelineClip[];
  total_duration: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Jobs
// ─────────────────────────────────────────────────────────────────────────────

export interface JobProgressEvent {
  job_id: string;
  seq: number;
  stage: string;
  stage_progress: number;
  overall_progress: number;
  current_frame?: number;
  total_frames?: number;
  preview_url?: string;
  eta_seconds?: number;
  message?: string;
}

export interface Job {
  id: string;
  type: JobType;
  status: JobStatus;
  clip_ids: string[];
  scene_ids: string[];
  depends_on: string[];
  generator_id?: string;
  generator_config?: Record<string, unknown>;
  vram_gb_required: number;
  created_at: number;
  started_at?: number;
  completed_at?: number;
  artifact_paths: string[];
  error_message?: string;
  last_seq: number;
  last_progress: number;
}

export interface JobQueue {
  jobs: Job[];
  active_job_id?: string;
  vram_in_use_gb: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Project State
// ─────────────────────────────────────────────────────────────────────────────

export interface VideoProject {
  id: string;
  name: string;
  version: string;
  settings: ProjectSettings;
  library: AssetLibrary;
  story: Story;
  timeline: Timeline;
  job_queue: JobQueue;
  created_at: number;
  updated_at: number;
  root_path?: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Generator Capabilities
// ─────────────────────────────────────────────────────────────────────────────

export interface GeneratorCapabilities {
  id: string;
  title: string;
  description?: string;
  version: string;
  generator_type: GeneratorType;
  vram_gb_min: number;
  vram_gb_recommended: number;
  ram_gb_min: number;
  supported_formats: string[];
  supports_ip_adapter: boolean;
  supports_lora: boolean;
  max_subjects: number;
  accepts_text_prompt: boolean;
  accepts_negative_prompt: boolean;
  supports_i2v: boolean;
  supports_t2v: boolean;
  supports_flf: boolean;
  supports_preview_mode: boolean;
  supports_camera_control: boolean;
  supported_control_nets: string[];
  valid_resolutions: [number, number][];
  resolution_must_be_divisible_by: number;
  max_frames: number;
  max_duration_seconds: number;
  supports_voice_cloning: boolean;
  supported_languages: string[];
  max_context_tokens: number;
  supports_streaming: boolean;
}

export interface GeneratorConfig {
  generator_id: string;
  model_path?: string;
  api_key?: string;
  api_base_url?: string;
  seed?: number;
  steps?: number;
  cfg_scale?: number;
  custom: Record<string, unknown>;
}

// ─────────────────────────────────────────────────────────────────────────────
// Recent Projects
// ─────────────────────────────────────────────────────────────────────────────

export interface RecentProject {
  id: string;
  name: string;
  path: string;
  opened_at: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper Functions
// ─────────────────────────────────────────────────────────────────────────────

export function createDefaultProjectSettings(): ProjectSettings {
  return {
    vram_target_gb: 24.0,
    canvas: {
      preset: '1080p_landscape',
      width: 1920,
      height: 1080,
      fps: 30,
      orientation: 'landscape',
    },
    default_generators: {},
  };
}

export function createDefaultAssetLibrary(): AssetLibrary {
  return {
    characters: [],
    props: [],
    voices: [],
    generated: [],
  };
}

export function createDefaultStory(): Story {
  return {
    scenes: [],
    created_at: Date.now() / 1000,
    updated_at: Date.now() / 1000,
  };
}

export function createDefaultTimeline(): Timeline {
  return {
    tracks: [
      {
        id: 'main',
        name: 'Main',
        type: 'video',
        order: 0,
        muted: false,
        locked: false,
      },
    ],
    clips: [],
    total_duration: 0,
  };
}

export function isClipAudioStale(clip: TimelineClip): boolean {
  if (!clip.audio_generated_at) return true;
  return (clip.script_edited_at || 0) > clip.audio_generated_at;
}

export function isClipVideoStale(clip: TimelineClip): boolean {
  if (!clip.video_generated_at) return true;
  if (isClipAudioStale(clip)) return true;
  return (
    Math.max(clip.keyframe_edited_at || 0, clip.style_edited_at || 0) > clip.video_generated_at
  );
}
