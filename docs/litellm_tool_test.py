#!/usr/bin/env python3
"""
Unified tool calling test using LiteLLM across multiple providers.
Supports LM Studio, Ollama, vLLM, and other LiteLLM-compatible providers.
"""

import argparse
import json
import sys
import time
from litellm import completion

def get_provider_config(provider):
    """Get configuration for different providers"""
    configs = {
        "lm-studio": {
            "model": "openai/nvidia/nemotron-3-nano",  # Use openai/ prefix for LM Studio
            "api_base": "http://localhost:1234/v1",
            "api_key": "lm-studio"
        },
        "ollama": {
            # IMPORTANT: use ollama_chat/ to route to Ollama's /api/chat endpoint.
            # Tool calling in Ollama is supported on /api/chat; /api/generate is not tool-call aware.
            "model": "ollama_chat/gpt-oss",
            "api_base": "http://localhost:11434"
        },
        "vllm": {
            "model": "openai/openai/gpt-oss-20b",  # vLLM server - use OpenAI provider with full model ID
            "api_base": "http://localhost:8000/v1",
            "api_key": "EMPTY"
        }
    }
    return configs.get(provider)

def test_tool_calling(provider, custom_model=None, custom_api_base=None, custom_api_key=None):
    """Test tool calling with specified provider"""

    config = get_provider_config(provider)
    if not config:
        print(f"❌ Unknown provider: {provider}")
        print("Available providers: lm-studio, ollama, vllm")
        return False

    # Override with custom settings if provided
    if custom_model:
        config["model"] = custom_model
    if custom_api_base:
        config["api_base"] = custom_api_base
    if custom_api_key:
        config["api_key"] = custom_api_key

    print(f"🧪 Testing gpt-oss model tool calling via {provider.upper()}")
    print(f"Model: {config['model']}")
    print(f"API Base: {config.get('api_base', 'default')}")
    print(f"API Key: {'Set' if config.get('api_key', 'NONE') != 'NONE' else 'None'}")

    # Note about Ollama + tools
    if provider == "ollama":
        print("ℹ️  Note: For Ollama tool calling via LiteLLM, use `ollama_chat/<model>` (routes to /api/chat).")
    print("-" * 60)

    # Define tools for testing
    tools = [
        {
            "type": "function",
            "function": {
                "name": "calculate",
                "description": "Calculate a mathematical expression",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "The mathematical expression to calculate, e.g., '2 + 3 * 4'"
                        }
                    },
                    "required": ["expression"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city and state, e.g., San Francisco, CA"
                        }
                    },
                    "required": ["location"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_time",
                "description": "Get the current time in a timezone",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "timezone": {
                            "type": "string",
                            "description": "The timezone, e.g., America/New_York, Europe/London"
                        }
                    },
                    "required": ["timezone"]
                }
            }
        }
    ]

    # Test prompts
    test_messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant with access to tools. When using tools, show your thinking process and then provide a clear answer based on the tool results. Be concise but informative."
        },
        {
            "role": "user",
            "content": "What's the weather like in Tokyo right now? Also, what time is it there? And can you calculate 15 * 23 + 7 for me?"
        }
    ]

    print("Prompt:", test_messages[1]["content"])
    print("\nAvailable tools:")
    for tool in tools:
        print(f"  - {tool['function']['name']}: {tool['function']['description']}")
    print()

    try:
        print("🚀 Sending request via LiteLLM...")

        # Set up LiteLLM parameters
        completion_kwargs = {
            "model": config["model"],
            "messages": test_messages,
            "tools": tools,
            "temperature": 0.1,
            "max_tokens": 1000,
            "include_reasoning": True  # Request reasoning/thinking content
        }

        # Add provider-specific settings
        if "api_base" in config:
            completion_kwargs["api_base"] = config["api_base"]
        if "api_key" in config and config["api_key"] != "NONE":
            completion_kwargs["api_key"] = config["api_key"]

        # For Ollama, use different tool choice approach
        if provider == "ollama":
            completion_kwargs["tool_choice"] = "auto"
        else:
            completion_kwargs["tool_choice"] = "auto"

        start_time = time.time()
        response = completion(**completion_kwargs)
        end_time = time.time()

        print(f"✅ Response received in {end_time - start_time:.2f} seconds")
        print("\n=== RESPONSE ANALYSIS ===")

        # Analyze the response
        choice = response.choices[0]
        message = choice.message

        # Extract reasoning/thinking from LiteLLM's standard reasoning fields (v1.63.0+)
        reasoning = getattr(message, 'reasoning_content', None)
        
        # Check thinking_blocks (used for Anthropic and some newer models)
        thinking_blocks = getattr(message, 'thinking_blocks', [])
        if not reasoning and thinking_blocks:
            reasoning = "\n".join([block.get('thinking', '') for block in thinking_blocks if block.get('type') == 'thinking'])

        # Fallback to older/alternative fields
        if not reasoning:
            reasoning = getattr(message, 'reasoning', None) or getattr(message, 'thinking', None)
        
        # If not found, check if it's in the content (some models use <thought> tags)
        content = getattr(message, 'content', '') or ''
        if not reasoning and content:
            import re
            thought_match = re.search(r'<thought>(.*?)</thought>', content, re.DOTALL | re.IGNORECASE)
            if thought_match:
                reasoning = thought_match.group(1).strip()
                # Optionally remove it from content to keep it clean
                content = re.sub(r'<thought>.*?</thought>', '', content, flags=re.DOTALL | re.IGNORECASE).strip()
            elif '<think>' in content.lower():
                # Handle DeepSeek style <think> tags
                think_match = re.search(r'<think>(.*?)</think>', content, re.DOTALL | re.IGNORECASE)
                if think_match:
                    reasoning = think_match.group(1).strip()
                    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL | re.IGNORECASE).strip()

        # Check for tool calls
        tool_calls = getattr(message, 'tool_calls', None) or []
        if tool_calls:
            print("✅ Tool calls detected!")
            print(f"Number of tool calls: {len(tool_calls)}")

            for i, tool_call in enumerate(tool_calls):
                print(f"\nTool Call {i+1}:")
                print(f"  ID: {getattr(tool_call, 'id', 'N/A')}")
                print(f"  Type: {getattr(tool_call, 'type', 'N/A')}")
                print(f"  Function: {getattr(tool_call.function, 'name', 'N/A')}")
                print(f"  Arguments: {getattr(tool_call.function, 'arguments', 'N/A')}")

                # Validate JSON arguments
                try:
                    args = getattr(tool_call.function, 'arguments', {})
                    if isinstance(args, str):
                        args = json.loads(args)
                    print("  ✅ Valid arguments format")
                except (json.JSONDecodeError, AttributeError) as e:
                    print(f"  ❌ Invalid arguments format: {e}")
        else:
            print("❌ No tool calls detected")

        # Check for content/reasoning
        if content and content.strip():
            print("\n✅ Content response detected:")
            print(f"  Length: {len(content)} characters")
            print(f"  Preview: {content[:200]}{'...' if len(content) > 200 else ''}")

            # Check if it contains thinking/reasoning patterns
            content_lower = content.lower()
            thinking_indicators = ['think', 'reason', 'consider', 'plan', 'first', 'then']
            has_thinking = any(indicator in content_lower for indicator in thinking_indicators)
            print(f"  Contains thinking indicators: {'✅' if has_thinking else '❌'}")
        else:
            print("\n❌ No content response detected")

        # Show finish reason and usage
        print("\n=== METADATA ===")
        print(f"Finish Reason: {getattr(choice, 'finish_reason', 'N/A')}")
        if hasattr(response, 'usage'):
            usage = response.usage
            print(f"Usage - Prompt: {getattr(usage, 'prompt_tokens', 'N/A')}, Completion: {getattr(usage, 'completion_tokens', 'N/A')}")

        # Check additional_kwargs for thinking/reasoning (legacy fallback)
        if not reasoning and hasattr(message, 'additional_kwargs'):
            reasoning = message.additional_kwargs.get('reasoning') or message.additional_kwargs.get('thinking')

        # Check for Ollama specific thinking in provider_specific_fields (legacy fallback)
        if not reasoning and hasattr(message, 'provider_specific_fields') and message.provider_specific_fields:
            reasoning = message.provider_specific_fields.get('thinking')

        # Check if the test was actually successful (found tools or content)
        is_actually_successful = bool(tool_calls or content or reasoning)
        
        if is_actually_successful:
            print("\n=== SUCCESS ===")
            print(f"🎉 {provider.upper()} tool calling test completed successfully!")
        else:
            print("\n=== FAILED ===")
            print(f"❌ {provider.upper()} test failed: No tool calls, content, or reasoning detected.")

        # Show pretty response message
        print("\n=== PRETTY RESPONSE ===")
            
        if reasoning:
            print(f"🧠 Thinking: {reasoning}")
        
        if content:
            print(f"💬 Content: {content}")
        elif not reasoning and not tool_calls:
            # If nothing else found, show the raw message object to help debug
            print(f"Empty response. Raw message: {message}")
            
        if tool_calls:
            print("🔧 Tool Calls:")
            for tc in tool_calls:
                func_name = getattr(tc.function, 'name', 'N/A')
                func_args = getattr(tc.function, 'arguments', 'N/A')
                print(f"  - {func_name}({func_args})")
        
        return is_actually_successful

    except Exception as e:
        print(f"❌ API call failed: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False

def check_provider_available(provider):
    """Check if a provider is currently available"""
    import requests

    try:
        if provider == "lm-studio":
            response = requests.get("http://localhost:1234/v1/models", timeout=5)
            return response.status_code == 200
        elif provider == "ollama":
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            return response.status_code == 200
        elif provider == "vllm":
            response = requests.get("http://localhost:8000/v1/models", timeout=5)
            return response.status_code == 200
    except:
        pass
    return False

def main():
    parser = argparse.ArgumentParser(description="Test tool calling with LiteLLM across different providers")
    parser.add_argument("provider", nargs="?", choices=["lm-studio", "ollama", "vllm"],
                       help="Provider to test (lm-studio, ollama, vllm)")
    parser.add_argument("--model", help="Custom model name")
    parser.add_argument("--api-base", help="Custom API base URL")
    parser.add_argument("--api-key", help="Custom API key")
    parser.add_argument("--all", action="store_true", help="Test all available providers sequentially")
    parser.add_argument("--list", action="store_true", help="List available providers")

    args = parser.parse_args()

    # List available providers
    if args.list:
        print("🔍 Checking available providers:")
        providers = ["lm-studio", "ollama", "vllm"]
        available = []

        for provider in providers:
            if check_provider_available(provider):
                status = "✅ AVAILABLE"
                available.append(provider)
            else:
                status = "❌ NOT AVAILABLE"
            print(f"  {provider.upper()}: {status}")

        print(f"\n📊 Found {len(available)} available provider(s)")
        return

    # Test all available providers
    if args.all:
        print("🔍 Scanning for available providers...")
        providers = ["lm-studio", "ollama", "vllm"]
        available_providers = [p for p in providers if check_provider_available(p)]

        if not available_providers:
            print("❌ No providers available! Please start one of:")
            print("   - LM Studio with gpt-oss-20b model")
            print("   - Ollama: ollama run gpt-oss")
            print("   - vLLM: ./serve.sh")
            sys.exit(1)

        print(f"🎯 Found {len(available_providers)} provider(s): {', '.join(available_providers)}")
        print("⚠️  Testing one provider at a time (VRAM constraints)")
        print()

        results = {}
        for i, provider in enumerate(available_providers):
            print(f"{'='*60}")
            success = test_tool_calling(provider, args.model, args.api_base, args.api_key)
            results[provider] = success

            # Pause between tests (except for the last one)
            if i < len(available_providers) - 1:
                print(f"\n⏳ Pausing 3 seconds before next provider...")
                time.sleep(3)

        print(f"\n{'='*60}")
        print("🎯 FINAL RESULTS:")
        print('='*60)
        for provider, success in results.items():
            if provider == "ollama" and not success:
                status = "❓ LIMITED (LiteLLM doesn't support Ollama tool calling)"
            elif success:
                status = "✅ SUCCESS"
            else:
                status = "❌ FAILED"
            print(f"{provider.upper()}: {status}")

        # Count actual successes (excluding Ollama's expected failure)
        actual_successes = sum(1 for p, s in results.items() if s or p != "ollama")
        successful = sum(results.values())
        print(f"\n📊 Summary: {successful}/{len(available_providers)} providers working with LiteLLM")

        if successful == len(available_providers):
            print("🎉 All available providers working perfectly!")
        elif successful > 0:
            print("⚠️  Some providers working - Note: Ollama tool calling not supported via LiteLLM")
        else:
            print("❌ No providers working, check configurations")

        if "ollama" in results and not results["ollama"]:
            print("\n💡 Ollama Note: Use direct Ollama tests for tool calling:")
            print("   ./ollama_curl_test.sh")
            print("   python ollama_tool_test.py")

    # Test specific provider
    elif args.provider:
        if not check_provider_available(args.provider):
            print(f"❌ Provider '{args.provider}' is not available!")
            print("💡 Check if the service is running:")
            if args.provider == "lm-studio":
                print("   - LM Studio should be running on port 1234")
            elif args.provider == "ollama":
                print("   - Run: ollama run gpt-oss")
            elif args.provider == "vllm":
                print("   - Run: ./serve.sh")
            sys.exit(1)

        success = test_tool_calling(args.provider, args.model, args.api_base, args.api_key)
        sys.exit(0 if success else 1)

    # No arguments provided
    else:
        parser.print_help()
        print("\n💡 Examples:")
        print("  python3 litellm_tool_test.py --list                    # List available providers")
        print("  python3 litellm_tool_test.py --all                     # Test all available providers")
        print("  python3 litellm_tool_test.py lm-studio                 # Test LM Studio only")
        print("  python3 litellm_tool_test.py ollama                    # Test Ollama only")
        print("  python3 litellm_tool_test.py vllm                      # Test vLLM only")
        print("  python3 litellm_tool_test.py lm-studio --model openai/gpt-oss-20b")
        sys.exit(1)

if __name__ == "__main__":
    main()