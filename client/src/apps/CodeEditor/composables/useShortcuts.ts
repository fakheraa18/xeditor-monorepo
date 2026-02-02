import { onMounted, onUnmounted } from 'vue';
import { shortcutManager } from '../core/shortcuts/ShortcutManager';
import type { ShortcutBinding, ShortcutScope } from '../core/shortcuts/types';

/**
 * Composable for managing shortcuts in components
 */
export function useShortcuts() {
  function register(binding: ShortcutBinding): void {
    shortcutManager.register(binding);
  }

  function unregister(id: string): void {
    shortcutManager.unregister(id);
  }

  function pushScope(scope: ShortcutScope, priority?: number): void {
    shortcutManager.pushScope(scope, priority);
  }

  function popScope(scope: ShortcutScope): void {
    shortcutManager.popScope(scope);
  }

  function isScopeActive(scope: ShortcutScope): boolean {
    return shortcutManager.isScopeActive(scope);
  }

  /**
   * Register a shortcut and automatically unregister it on unmount
   */
  function useShortcut(binding: ShortcutBinding) {
    register(binding);
    onUnmounted(() => {
      unregister(binding.id);
    });
  }

  /**
   * Manage a scope lifecycle (push on mount, pop on unmount)
   */
  function useScope(scope: ShortcutScope, priority?: number) {
    onMounted(() => {
      pushScope(scope, priority);
    });
    onUnmounted(() => {
      popScope(scope);
    });
  }

  return {
    register,
    unregister,
    pushScope,
    popScope,
    isScopeActive,
    useShortcut,
    useScope,
  };
}

