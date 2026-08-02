const BASE = "";

export async function api<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body: unknown = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export type JobStatus = {
  id: string;
  kind: string;
  status: "running" | "done" | "error";
  progress?: { fase?: string; mensaje?: string; hecho?: number; total?: number };
  result?: Record<string, unknown>;
  error?: string | null;
};

export async function pollJob(
  path: string,
  onTick?: (job: JobStatus) => void,
  intervalMs = 1200
): Promise<JobStatus> {
  for (;;) {
    const job = await api<JobStatus>(path);
    onTick?.(job);
    if (job.status === "done" || job.status === "error") return job;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
}
