<template>
  <q-layout view="hHh lpR fFf">
    <q-page-container>
      <q-page class="flex flex-center bg-grey-2">
        <div class="column items-center q-gutter-y-xl">
          <div class="text-h2 text-weight-bold text-primary">XEditor</div>

          <div class="row q-gutter-xl">
            <!-- Code Editor Card -->
            <q-card class="app-card cursor-pointer" @click="$router.push('/code')">
              <q-card-section class="column items-center q-pa-xl">
                <q-icon name="code" size="100px" color="primary" />
                <div class="text-h4 q-mt-md">Code Editor</div>
              </q-card-section>
            </q-card>

            <!-- Video Editor Card - Only shown when dev=true -->
            <q-card
              v-if="showVideoEditor"
              class="app-card cursor-pointer"
              @click="$router.push('/video')"
            >
              <q-card-section class="column items-center q-pa-xl">
                <q-icon name="movie" size="100px" color="secondary" />
                <div class="text-h4 q-mt-md">Video Editor</div>
              </q-card-section>
            </q-card>
          </div>
        </div>
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';

const route = useRoute();
const router = useRouter();

const showVideoEditor = computed(() => route.query.dev === 'true');

onMounted(() => {
  // Redirect to /code if dev parameter is not present
  if (!showVideoEditor.value) {
    void router.replace('/code');
  }
});
</script>

<style scoped>
.app-card {
  transition:
    transform 0.2s,
    box-shadow 0.2s;
  width: 300px;
}
.app-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 10px 20px rgba(0, 0, 0, 0.1);
}
</style>
