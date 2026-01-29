<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="!companionStore.isConnected" class="connection-overlay">
        <div class="connection-dialog">
          <div class="connection-icon">
            <q-spinner-dots
              v-if="companionStore.isConnecting"
              size="64px"
              color="primary"
            />
            <q-icon
              v-else
              name="link_off"
              size="64px"
              color="grey-5"
            />
          </div>

          <h5 class="connection-title">
            {{ companionStore.isConnecting ? 'Connecting...' : 'Local Companion Required' }}
          </h5>

          <p class="connection-message">
            {{ companionStore.isConnecting
              ? 'Attempting to connect to the local companion server...'
              : 'XEditor requires the local companion server to be running for AI features, indexing, and file operations.'
            }}
          </p>

          <div v-if="companionStore.error" class="connection-error">
            <q-icon name="error" color="negative" />
            <span>{{ companionStore.error }}</span>
          </div>

          <div class="connection-settings q-mt-md">
            <q-input
              v-model.number="portInput"
              label="Server Port"
              type="number"
              outlined
              dense
              class="q-mb-md"
              style="width: 200px;"
            />
            
            <q-btn
              color="primary"
              :label="companionStore.isConnecting ? 'Connecting...' : 'Connect'"
              :loading="companionStore.isConnecting"
              :disable="companionStore.isConnecting"
              @click="handleConnect"
            />
          </div>

          <q-separator class="q-my-lg" />

          <div class="connection-instructions">
            <div class="text-subtitle2 q-mb-sm">How to start the companion:</div>
            <div class="code-block">
              <code>
cd server<br />
pip install -r requirements.txt<br />
python main.py --port {{ portInput }}
              </code>
            </div>
          </div>

          <div class="connection-status q-mt-md">
            <q-chip
              :color="companionStore.isConnecting ? 'orange' : 'grey-5'"
              text-color="white"
              :icon="companionStore.isConnecting ? 'sync' : 'link_off'"
              size="sm"
            >
              {{ companionStore.isConnecting ? 'Connecting' : 'Disconnected' }}
            </q-chip>
            <span class="text-caption text-grey-6 q-ml-sm">
              {{ companionStore.url }}
            </span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import { useLocalCompanionStore } from '../stores/localCompanion';

const companionStore = useLocalCompanionStore();

const portInput = ref(companionStore.port);

// Sync port changes
watch(() => companionStore.port, (newPort) => {
  portInput.value = newPort;
});

async function handleConnect() {
  // Update port if changed
  if (portInput.value !== companionStore.port) {
    companionStore.setPort(portInput.value);
  }
  await companionStore.connect();
}
</script>

<style scoped>
.connection-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
}

.connection-dialog {
  background: white;
  border-radius: 12px;
  padding: 32px 40px;
  max-width: 500px;
  width: 90%;
  text-align: center;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

.connection-icon {
  margin-bottom: 16px;
}

.connection-title {
  margin: 0 0 12px 0;
  font-weight: 600;
  color: #333;
}

.connection-message {
  margin: 0;
  color: #666;
  font-size: 14px;
  line-height: 1.5;
}

.connection-error {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 16px;
  padding: 8px 16px;
  background: #ffebee;
  border-radius: 6px;
  color: #c62828;
  font-size: 13px;
}

.connection-settings {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.connection-instructions {
  text-align: left;
}

.code-block {
  background: #263238;
  border-radius: 6px;
  padding: 12px 16px;
  overflow-x: auto;
}

.code-block code {
  color: #aed581;
  font-family: 'Fira Code', 'Monaco', 'Menlo', monospace;
  font-size: 12px;
  line-height: 1.6;
}

.connection-status {
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
