<template>
  <q-layout view="hHh lpR fFf">
    <q-page-container>
      <router-view />
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
// The layout is minimal because VideoEditorPage handles its own layout
// when a project is open (including toolbar, drawers, etc.)
</script>
