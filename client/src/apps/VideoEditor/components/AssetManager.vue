<template>
  <div class="asset-manager">
    <div class="row items-center q-mb-md">
      <div class="text-h5">Asset Manager</div>
      <q-space />
      <q-btn-group>
        <q-btn
          :flat="activeCategory !== 'characters'"
          :color="activeCategory === 'characters' ? 'primary' : 'grey'"
          icon="person"
          label="Characters"
          @click="activeCategory = 'characters'"
        />
        <q-btn
          :flat="activeCategory !== 'props'"
          :color="activeCategory === 'props' ? 'primary' : 'grey'"
          icon="category"
          label="Props"
          @click="activeCategory = 'props'"
        />
        <q-btn
          :flat="activeCategory !== 'voices'"
          :color="activeCategory === 'voices' ? 'primary' : 'grey'"
          icon="record_voice_over"
          label="Voices"
          @click="activeCategory = 'voices'"
        />
      </q-btn-group>
    </div>

    <!-- Characters Grid -->
    <div v-if="activeCategory === 'characters'" class="assets-grid">
      <q-card v-for="char in library.characters" :key="char.id" class="asset-card" flat bordered>
        <q-card-section class="text-center">
          <q-avatar size="80px" color="primary" text-color="white">
            <img v-if="char.image_path" :src="char.image_path" />
            <span v-else>{{ char.name.charAt(0).toUpperCase() }}</span>
          </q-avatar>
          <div class="text-subtitle1 q-mt-sm">{{ char.name }}</div>
          <div class="text-caption text-grey">{{ char.code }}</div>
        </q-card-section>
        <q-card-actions align="center">
          <q-btn flat size="sm" icon="edit" @click="editCharacter(char)" />
          <q-btn flat size="sm" icon="image" @click="uploadCharacterImage(char)" />
          <q-btn flat size="sm" icon="mic" @click="uploadVoiceSample(char)" />
          <q-btn flat size="sm" icon="delete" color="negative" @click="deleteCharacter(char)" />
        </q-card-actions>
      </q-card>

      <q-card class="asset-card add-card" flat bordered @click="addCharacter">
        <q-card-section class="text-center flex flex-center" style="height: 100%">
          <div>
            <q-icon name="add" size="48px" color="grey" />
            <div class="text-grey q-mt-sm">Add Character</div>
          </div>
        </q-card-section>
      </q-card>
    </div>

    <!-- Props Grid -->
    <div v-if="activeCategory === 'props'" class="assets-grid">
      <q-card v-for="prop in library.props" :key="prop.id" class="asset-card" flat bordered>
        <q-card-section class="text-center">
          <q-icon name="image" size="64px" color="grey" />
          <div class="text-subtitle1 q-mt-sm">{{ prop.name }}</div>
          <div class="text-caption text-grey">{{ prop.category || 'Uncategorized' }}</div>
        </q-card-section>
        <q-card-actions align="center">
          <q-btn flat size="sm" icon="edit" />
          <q-btn flat size="sm" icon="upload" />
          <q-btn flat size="sm" icon="delete" color="negative" />
        </q-card-actions>
      </q-card>

      <q-card class="asset-card add-card" flat bordered @click="addProp">
        <q-card-section class="text-center flex flex-center" style="height: 100%">
          <div>
            <q-icon name="add" size="48px" color="grey" />
            <div class="text-grey q-mt-sm">Add Prop</div>
          </div>
        </q-card-section>
      </q-card>
    </div>

    <!-- Voices Grid -->
    <div v-if="activeCategory === 'voices'" class="assets-grid">
      <q-card v-for="voice in library.voices" :key="voice.id" class="asset-card" flat bordered>
        <q-card-section class="text-center">
          <q-icon name="record_voice_over" size="64px" color="grey" />
          <div class="text-subtitle1 q-mt-sm">{{ voice.name }}</div>
          <div class="text-caption text-grey">{{ voice.language }}</div>
        </q-card-section>
        <q-card-actions align="center">
          <q-btn flat size="sm" icon="play_arrow" />
          <q-btn flat size="sm" icon="upload" />
          <q-btn flat size="sm" icon="delete" color="negative" />
        </q-card-actions>
      </q-card>

      <q-card class="asset-card add-card" flat bordered @click="addVoice">
        <q-card-section class="text-center flex flex-center" style="height: 100%">
          <div>
            <q-icon name="add" size="48px" color="grey" />
            <div class="text-grey q-mt-sm">Add Voice</div>
          </div>
        </q-card-section>
      </q-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useVideoProjectStore } from '../stores';
import type { CharacterAsset } from '../types';

const projectStore = useVideoProjectStore();

const activeCategory = ref<'characters' | 'props' | 'voices'>('characters');
const library = computed(() => projectStore.library);

function addCharacter(): void {
  const name = prompt('Character name:');
  if (!name) return;
  const code = prompt('Character code:');
  if (!code) return;

  projectStore.addCharacter({ name, code });
}

function editCharacter(char: CharacterAsset): void {
  const name = prompt('Character name:', char.name);
  if (name) {
    projectStore.updateCharacter(char.id, { name });
  }
}

function uploadCharacterImage(char: CharacterAsset): void {
  // TODO: Implement file upload
  console.log('Upload image for', char.name);
}

function uploadVoiceSample(char: CharacterAsset): void {
  // TODO: Implement voice sample upload
  console.log('Upload voice sample for', char.name);
}

function deleteCharacter(char: CharacterAsset): void {
  if (confirm(`Delete character "${char.name}"?`)) {
    projectStore.removeCharacter(char.id);
  }
}

function addProp(): void {
  const name = prompt('Prop name:');
  if (!name) return;
  const code = prompt('Prop code:');
  if (!code) return;

  projectStore.addProp({ name, code });
}

function addVoice(): void {
  const name = prompt('Voice name:');
  if (!name) return;
  const code = prompt('Voice code:');
  if (!code) return;

  projectStore.addVoice({ name, code, sample_path: '', language: 'en' });
}
</script>

<style scoped lang="scss">
.asset-manager {
  max-width: 1200px;
  margin: 0 auto;
}

.assets-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
}

.asset-card {
  min-height: 180px;

  &.add-card {
    cursor: pointer;
    border-style: dashed;

    &:hover {
      background: rgba(0, 0, 0, 0.02);
    }
  }
}
</style>
