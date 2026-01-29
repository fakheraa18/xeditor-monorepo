import type { ChatMessage, ModelConfig, ResolvedPrompt } from '../types';
import { CompanionAdapter } from './CompanionAdapter';
import type { ChatResponse } from './ModelAdapter';

/**
 * Simplified Model Gateway that routes all requests through the Local Companion.
 * All LLM providers are now handled by the Python companion server.
 */
class ModelGateway {
  private adapter = new CompanionAdapter();

  async sendMessage(
    messages: ChatMessage[],
    model: ModelConfig,
    promptConfig: ResolvedPrompt,
    signal?: AbortSignal,
  ): Promise<ChatResponse> {
    return this.adapter.sendMessage(messages, model, promptConfig, signal);
  }

  async streamMessage(
    messages: ChatMessage[],
    model: ModelConfig,
    promptConfig: ResolvedPrompt,
    onChunk: (chunk: string) => void,
    signal?: AbortSignal,
  ): Promise<ChatResponse> {
    return this.adapter.streamMessage(messages, model, promptConfig, onChunk, signal);
  }
}

let gatewayInstance: ModelGateway | null = null;

/**
 * Get the shared ModelGateway instance.
 * This ensures all parts of the app use the same configured gateway.
 */
export function getModelGateway(): ModelGateway {
  if (!gatewayInstance) {
    gatewayInstance = new ModelGateway();
  }
  return gatewayInstance;
}
