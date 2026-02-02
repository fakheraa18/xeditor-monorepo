<template>
  <q-dialog ref="dialogRef" @hide="onDialogHide" persistent>
    <q-card style="min-width: 420px; max-width: 90vw">
      <q-card-section class="q-pb-sm">
        <div class="text-h6">Save changes?</div>
      </q-card-section>

      <q-card-section class="q-pt-none">
        <div class="text-body2">
          Do you want to save the changes you made to <span class="text-weight-medium">"{{ fileName }}"</span
          >?
        </div>
      </q-card-section>

      <q-separator />

      <q-card-actions align="right" class="q-px-md q-py-sm">
        <q-btn
          flat
          color="negative"
          label="Don't Save & Close"
          @click="onDialogOK('discard')"
        />
        <q-btn flat color="primary" label="Save & Close" @click="onDialogOK('save')" />
        <q-btn flat color="grey-7" label="Cancel" @click="onDialogCancel" />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { useDialogPluginComponent } from 'quasar';

export type SaveChangesAction = 'save' | 'discard';

defineProps<{
  fileName: string;
}>();

defineEmits([...useDialogPluginComponent.emits]);

const { dialogRef, onDialogHide, onDialogOK, onDialogCancel } = useDialogPluginComponent();
</script>


