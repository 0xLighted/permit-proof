import type { TechnicianState, SupervisorState, AuditEvent } from './types';

export class ApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export async function fetchState<T = TechnicianState | SupervisorState>(): Promise<T> {
  const res = await fetch('/api/state', {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.error || `Failed to fetch state (${res.status})`, res.status);
  }
  return res.json();
}

export async function postAction<T = TechnicianState | SupervisorState>(
  action: string,
  payload: Record<string, unknown> = {}
): Promise<T> {
  const res = await fetch('/api/action', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({ action, ...payload }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.error || `Action failed (${res.status})`, res.status);
  }
  return res.json();
}

export async function fetchAuditLog(): Promise<AuditEvent[]> {
  const res = await fetch('/api/audit-log', {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.error || `Failed to fetch audit log (${res.status})`, res.status);
  }
  return res.json();
}
