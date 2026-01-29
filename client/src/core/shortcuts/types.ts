export type ShortcutScope = string;

export type KeyCombo = string; // e.g., "ctrl+p", "cmd+w", "ctrl+shift+k"

export interface ShortcutBinding {
  id: string;
  combo: KeyCombo;
  handler: (event: KeyboardEvent) => void | Promise<void>;
  scope: ShortcutScope;
  priority?: number; // Higher priority wins. Default: 0
  when?: () => boolean; // Condition to check before executing
  allowInInputs?: boolean; // If false, ignores when focus is in input/textarea/select
}

export interface ParsedKeyCombo {
  ctrl: boolean;
  meta: boolean; // Cmd on Mac
  shift: boolean;
  alt: boolean;
  key: string; // The actual key (lowercase)
}

