import type { ChatMessage, ModelConfig, ResolvedPrompt } from '../types';

export interface ChatResponse {
  content: string;
  finishReason?: string;
  usage?: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Abstract Adapter
// ─────────────────────────────────────────────────────────────────────────────

export abstract class ModelAdapter {
  abstract sendMessage(
    messages: ChatMessage[],
    config: ModelConfig,
    promptConfig: ResolvedPrompt,
    signal?: AbortSignal,
  ): Promise<ChatResponse>;

  abstract streamMessage(
    messages: ChatMessage[],
    config: ModelConfig,
    promptConfig: ResolvedPrompt,
    onChunk: (chunk: string) => void,
    signal?: AbortSignal,
  ): Promise<ChatResponse>;
}
