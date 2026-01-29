import type { ChatMessage, ModelConfig, ResolvedPrompt } from '../types';
import { ModelAdapter, type ChatResponse } from './ModelAdapter';
import { useLocalCompanionStore } from '../../stores/localCompanion';

/**
 * Adapter that routes all LLM requests to the local Python companion server.
 * This is the primary (and now only) adapter for LLM communication.
 */
export class CompanionAdapter extends ModelAdapter {
  async sendMessage(
    messages: ChatMessage[],
    config: ModelConfig,
    promptConfig: ResolvedPrompt,
    _signal?: AbortSignal,
  ): Promise<ChatResponse> {
    const companionStore = useLocalCompanionStore();

    if (!companionStore.isConnected) {
      const connected = await companionStore.connect();
      if (!connected) {
        throw new Error(
          'Local Companion is not running. Please start the companion server and try again.',
        );
      }
    }

    try {
      const response = await companionStore.request<{
        content: string;
        finish_reason?: string;
        error?: string;
        usage?: {
          prompt_tokens: number;
          completion_tokens: number;
          total_tokens: number;
        };
      }>('llm_request_v2', {
        provider: config.provider,
        modelId: config.id,
        messages: messages.map((m) => ({ role: m.role, content: m.content })),
        temperature: promptConfig.temperature,
        maxTokens: promptConfig.maxTokens,
        // Local companion-only settings
        runner: config.localCompanion?.runner ?? 'vllm',
        hfToken: companionStore.huggingFaceToken,
        // Keep connection/auth for parity (even if unused for local_companion)
        connection: {
          baseUrl: config.connection.baseUrl,
          path: config.connection.path,
          headers: config.connection.headers,
        },
        auth: config.connection.auth,
        // Extra payload parameters
        extraPayload: config.extraPayload,
      });

      if (response.error) {
        throw new Error(`Companion LLM Error: ${response.error}`);
      }

      const chatResponse: ChatResponse = {
        content: response.content,
      };

      if (response.finish_reason) {
        chatResponse.finishReason = response.finish_reason;
      }

      if (response.usage) {
        chatResponse.usage = {
          promptTokens: response.usage.prompt_tokens,
          completionTokens: response.usage.completion_tokens,
          totalTokens: response.usage.total_tokens,
        };
      }

      return chatResponse;
    } catch (error) {
      console.error('Local Companion LLM Request Failed:', error);
      throw error;
    }
  }

  async streamMessage(
    messages: ChatMessage[],
    config: ModelConfig,
    promptConfig: ResolvedPrompt,
    onChunk: (chunk: string) => void,
    signal?: AbortSignal,
  ): Promise<ChatResponse> {
    const companionStore = useLocalCompanionStore();

    if (!companionStore.isConnected) {
      const connected = await companionStore.connect();
      if (!connected) {
        throw new Error(
          'Local Companion is not running. Please start the companion server and try again.',
        );
      }
    }

    try {
      let fullContent = '';

      const finalResponse = await companionStore.streamRequest<{
        content: string;
        finish_reason?: string;
        error?: string;
        usage?: {
          prompt_tokens: number;
          completion_tokens: number;
          total_tokens: number;
        };
      }>(
        'llm_stream_request_v2',
        {
          provider: config.provider,
          modelId: config.id,
          messages: messages.map((m) => ({ role: m.role, content: m.content })),
          temperature: promptConfig.temperature,
          maxTokens: promptConfig.maxTokens,
          runner: config.localCompanion?.runner ?? 'vllm',
          hfToken: companionStore.huggingFaceToken,
          connection: {
            baseUrl: config.connection.baseUrl,
            path: config.connection.path,
            headers: config.connection.headers,
          },
          auth: config.connection.auth,
          // Extra payload parameters
          extraPayload: config.extraPayload,
        },
        (chunk: unknown) => {
          // Chunks are strings from the server
          const chunkStr = typeof chunk === 'string' ? chunk : '';
          fullContent += chunkStr;
          onChunk(chunkStr);
        },
        signal,
      );

      if (finalResponse.error) {
        throw new Error(`Companion LLM Error: ${finalResponse.error}`);
      }

      const chatResponse: ChatResponse = {
        content: finalResponse.content || fullContent,
      };

      if (finalResponse.finish_reason) {
        chatResponse.finishReason = finalResponse.finish_reason;
      }

      if (finalResponse.usage) {
        chatResponse.usage = {
          promptTokens: finalResponse.usage.prompt_tokens,
          completionTokens: finalResponse.usage.completion_tokens,
          totalTokens: finalResponse.usage.total_tokens,
        };
      }

      return chatResponse;
    } catch (error) {
      console.error('Local Companion LLM Stream Request Failed:', error);
      throw error;
    }
  }
}
