/// <reference types="electron" />

declare namespace NodeJS {
  interface ProcessEnv {
    DEV?: string;
    DEBUGGING?: string;
    APP_URL?: string;
    QUASAR_ELECTRON_PRELOAD_FOLDER?: string;
    QUASAR_ELECTRON_PRELOAD_EXTENSION?: string;
    XEDITOR_PORT?: string;
    XEDITOR_HOST?: string;
  }
}
