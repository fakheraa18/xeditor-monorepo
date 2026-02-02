import type { ProjectId, ProjectRecord, ProjectSummary, EmbeddingModelId } from '../types';
import { useLocalCompanionStore } from '../../../../stores/localCompanion';

interface CompanionProjectFolder {
  id: string;
  name: string;
  path: string;
}

interface CompanionProject {
  id: string;
  name: string;
  safeName?: string;
  path: string;
  folders: CompanionProjectFolder[];
  folderCount?: number;
  createdAt: number;
  updatedAt: number;
  settings?: {
    embeddingModelId?: string;
  };
}

function toProjectRecord(companion: CompanionProject): ProjectRecord {
  const result: ProjectRecord = {
    id: companion.id,
    name: companion.name,
    createdAt: companion.createdAt,
    updatedAt: companion.updatedAt,
    folders: companion.folders.map((f) => ({
      id: f.id,
      name: f.name,
      systemPath: f.path,
      addedAt: companion.createdAt, // Use project creation time as fallback
    })),
  };

  // Convert settings with proper type casting
  if (companion.settings?.embeddingModelId) {
    result.settings = {
      embeddingModelId: companion.settings.embeddingModelId as EmbeddingModelId,
    };
  }

  return result;
}

function toProjectSummary(companion: CompanionProject): ProjectSummary {
  return {
    id: companion.id,
    name: companion.name,
    folderCount: companion.folderCount ?? companion.folders.length,
    updatedAt: companion.updatedAt,
  };
}

export async function listProjects(): Promise<ProjectSummary[]> {
  const companionStore = useLocalCompanionStore();
  const response = await companionStore.request<{
    success: boolean;
    projects: CompanionProject[];
  }>('list_projects', {});

  if (!response.success) {
    throw new Error('Failed to list projects');
  }

  return response.projects.map(toProjectSummary);
}

export async function getProject(projectId: ProjectId): Promise<ProjectRecord | null> {
  const companionStore = useLocalCompanionStore();
  const response = await companionStore.request<{
    success: boolean;
    project?: CompanionProject;
    error?: string;
  }>('get_project', { id: projectId });

  if (!response.success || !response.project) {
    return null;
  }

  return toProjectRecord(response.project);
}

export async function createProject(
  projectId: ProjectId,
  name: string,
  folders: Array<{ id: string; name: string; path: string }> = [],
): Promise<ProjectRecord> {
  const companionStore = useLocalCompanionStore();
  const response = await companionStore.request<{
    success: boolean;
    project?: CompanionProject;
    error?: string;
  }>('create_project', {
    id: projectId,
    name,
    folders,
  });

  if (!response.success || !response.project) {
    throw new Error(response.error ?? 'Failed to create project');
  }

  return toProjectRecord(response.project);
}

export async function updateProject(
  projectId: ProjectId,
  updates: {
    name?: string;
    folders?: Array<{ id: string; name: string; path: string }>;
    settings?: { embeddingModelId?: string };
  },
): Promise<ProjectRecord> {
  const companionStore = useLocalCompanionStore();
  const response = await companionStore.request<{
    success: boolean;
    project?: CompanionProject;
    error?: string;
  }>('update_project', {
    id: projectId,
    updates,
  });

  if (!response.success || !response.project) {
    throw new Error(response.error ?? 'Failed to update project');
  }

  return toProjectRecord(response.project);
}

export async function deleteProject(projectId: ProjectId): Promise<void> {
  const companionStore = useLocalCompanionStore();
  const response = await companionStore.request<{
    success: boolean;
    error?: string;
  }>('delete_project', { id: projectId });

  if (!response.success) {
    throw new Error(response.error ?? 'Failed to delete project');
  }
}
