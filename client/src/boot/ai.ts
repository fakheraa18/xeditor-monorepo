import { boot } from 'quasar/wrappers';

// AI initialization is now handled by the chat store and backend
// No need to initialize gateway here anymore
export default boot(() => {
  // Chat store will initialize on first use
  console.log('AI system ready (backend-managed)');
});

