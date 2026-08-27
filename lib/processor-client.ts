import type { ProjectJob, ProjectPreferences } from './contracts';

const PROCESSOR_URL = process.env.NEXT_PUBLIC_PROCESSOR_URL ?? 'http://127.0.0.1:8788';

export async function processorHealth(signal?: AbortSignal): Promise<boolean> {
  try {
    const response = await fetch(`${PROCESSOR_URL}/health`, { signal, cache: 'no-store' });
    return response.ok;
  } catch {
    return false;
  }
}

export async function createFileProject(file: File, preferences: ProjectPreferences): Promise<ProjectJob> {
  const form = new FormData();
  form.append('file', file);
  form.append('preferences', JSON.stringify(preferences));
  const response = await fetch(`${PROCESSOR_URL}/api/v1/projects/upload`, { method: 'POST', body: form });
  if (!response.ok) throw new Error(await readableError(response));
  return normalizeJob(await response.json() as ProjectJob);
}

export async function createUrlProject(url: string, preferences: ProjectPreferences): Promise<ProjectJob> {
  const response = await fetch(`${PROCESSOR_URL}/api/v1/projects/url`, {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ url, preferences }),
  });
  if (!response.ok) throw new Error(await readableError(response));
  return normalizeJob(await response.json() as ProjectJob);
}

export async function getProject(id: string): Promise<ProjectJob> {
  const response = await fetch(`${PROCESSOR_URL}/api/v1/projects/${id}`, { cache: 'no-store' });
  if (!response.ok) throw new Error(await readableError(response));
  return normalizeJob(await response.json() as ProjectJob);
}

function normalizeJob(job: ProjectJob): ProjectJob {
  return {
    ...job,
    clips: job.clips.map((clip) => ({
      ...clip,
      outputUrl: clip.outputUrl?.startsWith('/') ? `${PROCESSOR_URL}${clip.outputUrl}` : clip.outputUrl,
    })),
  };
}

async function readableError(response: Response): Promise<string> {
  try { const data = await response.json() as { detail?: string }; return data.detail ?? 'O processador recusou a solicitação.'; }
  catch { return 'Não foi possível conversar com o processador.'; }
}
