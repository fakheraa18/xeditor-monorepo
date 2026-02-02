import { ref } from 'vue';
import type { QScrollArea } from 'quasar';

export function useScroll() {
  const scrollAreaRef = ref<InstanceType<typeof QScrollArea> | null>(null);

  return {
    scrollAreaRef,
  };
}
