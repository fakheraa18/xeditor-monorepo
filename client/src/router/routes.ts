import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('pages/LauncherPage.vue'),
  },
  {
    path: '/code',
    component: () => import('../apps/CodeEditor/layouts/CodeEditorLayout.vue'),
    children: [
      { path: '', component: () => import('../apps/CodeEditor/pages/CodeEditorPage.vue') },
      { path: 'settings/ai', component: () => import('pages/AISettingsPage.vue') },
      { path: 'index-explorer', component: () => import('pages/IndexExplorerPage.vue') },
    ],
  },
  {
    path: '/video',
    component: () => import('../apps/VideoEditor/layouts/VideoEditorLayout.vue'),
    children: [
      { path: '', component: () => import('../apps/VideoEditor/pages/VideoEditorPage.vue') },
    ],
  },

  // Always leave this as last one,
  // but you can also remove it
  {
    path: '/:catchAll(.*)*',
    component: () => import('pages/ErrorNotFound.vue'),
  },
];

export default routes;
