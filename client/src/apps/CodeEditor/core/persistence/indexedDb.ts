import type {
  ProjectId,
  ProjectRecord,
  ProjectSummary,
  AiConfigRecord,
  ChatSession,
  ChatSessionId,
  ChatSessionSummary,
} from '../types';

const DB_NAME = 'xeditor';
const DB_VERSION = 3;

const STORE_PROJECTS = 'projects';
const STORE_META = 'meta';
const STORE_AI_CONFIG = 'aiConfig';
const STORE_CHAT_SESSIONS = 'chatSessions';

type MetaKey = 'lastOpenedProjectId';

interface MetaRecord {
  key: MetaKey;
  value: ProjectId | null;
}

function requestToPromise<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error('IndexedDB request failed'));
  });
}

function transactionDone(tx: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onabort = () => reject(tx.error ?? new Error('IndexedDB transaction aborted'));
    tx.onerror = () => reject(tx.error ?? new Error('IndexedDB transaction error'));
  });
}

async function openDb(): Promise<IDBDatabase> {
  const request = indexedDB.open(DB_NAME, DB_VERSION);

  request.onupgradeneeded = () => {
    const db = request.result;

    if (!db.objectStoreNames.contains(STORE_PROJECTS)) {
      db.createObjectStore(STORE_PROJECTS, { keyPath: 'id' });
    }

    if (!db.objectStoreNames.contains(STORE_META)) {
      db.createObjectStore(STORE_META, { keyPath: 'key' });
    }

    // V2: AI Config store
    if (!db.objectStoreNames.contains(STORE_AI_CONFIG)) {
      db.createObjectStore(STORE_AI_CONFIG, { keyPath: 'id' });
    }

    // V3: Chat Sessions store
    if (!db.objectStoreNames.contains(STORE_CHAT_SESSIONS)) {
      const chatStore = db.createObjectStore(STORE_CHAT_SESSIONS, { keyPath: 'id' });
      chatStore.createIndex('projectId', 'projectId', { unique: false });
      chatStore.createIndex('updatedAt', 'updatedAt', { unique: false });
    }
  };

  return await requestToPromise(request);
}

function toSummary(project: ProjectRecord): ProjectSummary {
  return {
    id: project.id,
    name: project.name,
    folderCount: project.folders.length,
    updatedAt: project.updatedAt,
  };
}

export async function listProjects(): Promise<ProjectSummary[]> {
  const db = await openDb();
  const tx = db.transaction(STORE_PROJECTS, 'readonly');
  const store = tx.objectStore(STORE_PROJECTS);
  const projects = await requestToPromise(store.getAll() as IDBRequest<ProjectRecord[]>);
  await transactionDone(tx);
  db.close();

  return projects.map(toSummary).sort((a, b) => b.updatedAt - a.updatedAt);
}

export async function getProject(projectId: ProjectId): Promise<ProjectRecord | null> {
  const db = await openDb();
  const tx = db.transaction(STORE_PROJECTS, 'readonly');
  const store = tx.objectStore(STORE_PROJECTS);
  const project = await requestToPromise(
    store.get(projectId) as IDBRequest<ProjectRecord | undefined>,
  );
  await transactionDone(tx);
  db.close();
  return project ?? null;
}

export async function putProject(project: ProjectRecord): Promise<void> {
  const db = await openDb();
  const tx = db.transaction(STORE_PROJECTS, 'readwrite');
  const store = tx.objectStore(STORE_PROJECTS);
  store.put(project);
  await transactionDone(tx);
  db.close();
}

export async function deleteProject(projectId: ProjectId): Promise<void> {
  const db = await openDb();
  const tx = db.transaction(STORE_PROJECTS, 'readwrite');
  const store = tx.objectStore(STORE_PROJECTS);
  store.delete(projectId);
  await transactionDone(tx);
  db.close();
}

export async function getLastOpenedProjectId(): Promise<ProjectId | null> {
  const db = await openDb();
  const tx = db.transaction(STORE_META, 'readonly');
  const store = tx.objectStore(STORE_META);
  const record = await requestToPromise(
    store.get('lastOpenedProjectId') as IDBRequest<MetaRecord | undefined>,
  );
  await transactionDone(tx);
  db.close();
  return record?.value ?? null;
}

export async function setLastOpenedProjectId(projectId: ProjectId | null): Promise<void> {
  const db = await openDb();
  const tx = db.transaction(STORE_META, 'readwrite');
  const store = tx.objectStore(STORE_META);
  const record: MetaRecord = { key: 'lastOpenedProjectId', value: projectId };
  store.put(record);
  await transactionDone(tx);
  db.close();
}

// ─────────────────────────────────────────────────────────────────────────────
// AI Config Persistence
// ─────────────────────────────────────────────────────────────────────────────

export async function getAiConfig(): Promise<AiConfigRecord | null> {
  const db = await openDb();
  const tx = db.transaction(STORE_AI_CONFIG, 'readonly');
  const store = tx.objectStore(STORE_AI_CONFIG);
  const record = await requestToPromise(
    store.get('global') as IDBRequest<AiConfigRecord | undefined>,
  );
  await transactionDone(tx);
  db.close();
  return record ?? null;
}

export async function putAiConfig(config: AiConfigRecord): Promise<void> {
  const db = await openDb();
  const tx = db.transaction(STORE_AI_CONFIG, 'readwrite');
  const store = tx.objectStore(STORE_AI_CONFIG);
  store.put(config);
  await transactionDone(tx);
  db.close();
}

// ─────────────────────────────────────────────────────────────────────────────
// Chat Sessions Persistence
// ─────────────────────────────────────────────────────────────────────────────

function toChatSessionSummary(session: ChatSession): ChatSessionSummary {
  return {
    id: session.id,
    projectId: session.projectId,
    title: session.title,
    createdAt: session.createdAt,
    updatedAt: session.updatedAt,
    turnCount: session.turns.length,
  };
}

export async function listChatSessions(projectId: ProjectId): Promise<ChatSessionSummary[]> {
  const db = await openDb();
  const tx = db.transaction(STORE_CHAT_SESSIONS, 'readonly');
  const store = tx.objectStore(STORE_CHAT_SESSIONS);
  const index = store.index('projectId');
  const sessions = await requestToPromise(
    index.getAll(projectId) as IDBRequest<ChatSession[]>,
  );
  await transactionDone(tx);
  db.close();

  return sessions.map(toChatSessionSummary).sort((a, b) => b.updatedAt - a.updatedAt);
}

export async function getChatSession(sessionId: ChatSessionId): Promise<ChatSession | null> {
  const db = await openDb();
  const tx = db.transaction(STORE_CHAT_SESSIONS, 'readonly');
  const store = tx.objectStore(STORE_CHAT_SESSIONS);
  const session = await requestToPromise(
    store.get(sessionId) as IDBRequest<ChatSession | undefined>,
  );
  await transactionDone(tx);
  db.close();
  return session ?? null;
}

export async function putChatSession(session: ChatSession): Promise<void> {
  const db = await openDb();
  const tx = db.transaction(STORE_CHAT_SESSIONS, 'readwrite');
  const store = tx.objectStore(STORE_CHAT_SESSIONS);
  store.put(session);
  await transactionDone(tx);
  db.close();
}

export async function deleteChatSession(sessionId: ChatSessionId): Promise<void> {
  const db = await openDb();
  const tx = db.transaction(STORE_CHAT_SESSIONS, 'readwrite');
  const store = tx.objectStore(STORE_CHAT_SESSIONS);
  store.delete(sessionId);
  await transactionDone(tx);
  db.close();
}

export async function deleteChatSessionsByProject(projectId: ProjectId): Promise<void> {
  const db = await openDb();
  const tx = db.transaction(STORE_CHAT_SESSIONS, 'readwrite');
  const store = tx.objectStore(STORE_CHAT_SESSIONS);
  const index = store.index('projectId');
  const sessions = await requestToPromise(
    index.getAll(projectId) as IDBRequest<ChatSession[]>,
  );

  for (const session of sessions) {
    store.delete(session.id);
  }

  await transactionDone(tx);
  db.close();
}
