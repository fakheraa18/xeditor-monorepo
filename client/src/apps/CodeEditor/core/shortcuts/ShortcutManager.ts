import type { ShortcutBinding, ShortcutScope, ParsedKeyCombo, KeyCombo } from './types';

export class ShortcutManager {
  private bindings: Map<string, ShortcutBinding> = new Map();
  private scopeStack: Array<{ scope: ShortcutScope; priority: number }> = [];
  private isEnabled = true;

  /**
   * Parse a key combo string like "ctrl+p" or "cmd+shift+k"
   */
  parseCombo(combo: KeyCombo): ParsedKeyCombo {
    const parts = combo.toLowerCase().split('+').map((p) => p.trim());
    const parsed: ParsedKeyCombo = {
      ctrl: false,
      meta: false,
      shift: false,
      alt: false,
      key: '',
    };

    for (const part of parts) {
      if (part === 'ctrl' || part === 'control') {
        parsed.ctrl = true;
      } else if (part === 'cmd' || part === 'meta') {
        parsed.meta = true;
      } else if (part === 'shift') {
        parsed.shift = true;
      } else if (part === 'alt' || part === 'option') {
        parsed.alt = true;
      } else {
        parsed.key = part;
      }
    }

    return parsed;
  }

  /**
   * Check if a keyboard event matches a parsed combo
   */
  matchesCombo(event: KeyboardEvent, parsed: ParsedKeyCombo): boolean {
    // Normalize key to lowercase for comparison
    const eventKey = event.key.toLowerCase();

    // Handle special keys - normalize parsed key for comparison
    let normalizedParsedKey = parsed.key;
    if (parsed.key === 'space') {
      normalizedParsedKey = ' ';
    }

    // Check if keys match
    if (normalizedParsedKey !== eventKey) {
      return false;
    }

    // Check modifiers
    if (parsed.ctrl && !event.ctrlKey) return false;
    if (parsed.meta && !event.metaKey) return false;
    if (parsed.shift && !event.shiftKey) return false;
    if (parsed.alt && !event.altKey) return false;

    // Ensure no extra modifiers are pressed
    if (!parsed.ctrl && event.ctrlKey) return false;
    if (!parsed.meta && event.metaKey) return false;
    if (!parsed.shift && event.shiftKey) return false;
    if (!parsed.alt && event.altKey) return false;

    return true;
  }

  /**
   * Register a shortcut binding
   */
  register(binding: ShortcutBinding): void {
    this.bindings.set(binding.id, binding);
  }

  /**
   * Unregister a shortcut binding
   */
  unregister(id: string): void {
    this.bindings.delete(id);
  }

  /**
   * Push a scope onto the scope stack
   */
  pushScope(scope: ShortcutScope, priority: number = 0): void {
    this.scopeStack.push({ scope, priority });
    // Sort by priority descending
    this.scopeStack.sort((a, b) => b.priority - a.priority);
  }

  /**
   * Pop a scope from the scope stack
   */
  popScope(scope: ShortcutScope): void {
    const index = this.scopeStack.findIndex((s) => s.scope === scope);
    if (index !== -1) {
      this.scopeStack.splice(index, 1);
    }
  }

  /**
   * Check if a scope is currently active
   */
  isScopeActive(scope: ShortcutScope): boolean {
    return this.scopeStack.some((s) => s.scope === scope);
  }

  /**
   * Get active scopes ordered by priority
   */
  getActiveScopes(): ShortcutScope[] {
    return this.scopeStack.map((s) => s.scope);
  }

  /**
   * Check if focus is in an input element
   */
  isInInputElement(event: KeyboardEvent): boolean {
    const target = event.target as HTMLElement;
    if (!target) return false;

    const tagName = target.tagName.toLowerCase();
    const isInput =
      tagName === 'input' ||
      tagName === 'textarea' ||
      tagName === 'select' ||
      target.isContentEditable;

    return isInput;
  }

  /**
   * Handle a keyboard event and dispatch to matching bindings
   */
  async handleKeyDown(event: KeyboardEvent): Promise<boolean> {
    if (!this.isEnabled) return false;

    const activeScopes = this.getActiveScopes();
    const parsedCombos = new Map<string, ParsedKeyCombo>();

    // Collect all bindings that might match, ordered by scope priority
    const candidates: Array<{ binding: ShortcutBinding; parsed: ParsedKeyCombo }> = [];

    // If there are active scopes (non-global), only process bindings in those scopes
    // This masks global shortcuts when modals/dialogs are open
    const hasNonGlobalScopes = activeScopes.length > 0 && !activeScopes.every((s) => s === 'global');

    for (const binding of this.bindings.values()) {
      // If non-global scopes are active, skip global bindings
      if (hasNonGlobalScopes && binding.scope === 'global') {
        continue;
      }

      // Check if binding's scope is active (or if it's global scope)
      if (binding.scope !== 'global' && !activeScopes.includes(binding.scope)) {
        continue;
      }

      // Check when condition
      if (binding.when && !binding.when()) {
        continue;
      }

      // Check if we should ignore inputs
      if (!binding.allowInInputs && this.isInInputElement(event)) {
        continue;
      }

      // Parse combo if not already parsed
      let parsed = parsedCombos.get(binding.combo);
      if (!parsed) {
        parsed = this.parseCombo(binding.combo);
        parsedCombos.set(binding.combo, parsed);
      }

      // Check if event matches
      if (this.matchesCombo(event, parsed)) {
        candidates.push({ binding, parsed });
      }
    }

    // Sort candidates by scope priority (highest first)
    candidates.sort((a, b) => {
      const aScopeIndex = activeScopes.indexOf(a.binding.scope);
      const bScopeIndex = activeScopes.indexOf(b.binding.scope);
      const aPriority = a.binding.priority ?? 0;
      const bPriority = b.binding.priority ?? 0;

      // If both are in active scopes, compare by scope order then binding priority
      if (aScopeIndex !== -1 && bScopeIndex !== -1) {
        if (aScopeIndex !== bScopeIndex) {
          return aScopeIndex - bScopeIndex; // Earlier in activeScopes = higher priority
        }
        return bPriority - aPriority;
      }

      // Global scope comes last
      if (a.binding.scope === 'global' && b.binding.scope !== 'global') return 1;
      if (b.binding.scope === 'global' && a.binding.scope !== 'global') return -1;

      return bPriority - aPriority;
    });

    // Execute the first matching binding
    if (candidates.length > 0) {
      const firstCandidate = candidates[0];
      if (firstCandidate) {
        const { binding } = firstCandidate;
        event.preventDefault();
        event.stopPropagation();
        await binding.handler(event);
        return true;
      }
    }

    return false;
  }

  /**
   * Enable/disable the shortcut manager
   */
  setEnabled(enabled: boolean): void {
    this.isEnabled = enabled;
  }

  /**
   * Clear all bindings
   */
  clear(): void {
    this.bindings.clear();
    this.scopeStack = [];
  }
}

// Singleton instance
export const shortcutManager = new ShortcutManager();

