export interface ChecklistItem {
  label: string;
  done: boolean;
}

export interface TaskItem {
  id: string;
  job_id: string;
  timestamp: string;
  supervisor_id: string;
  technician_id: string;
  technician: string;
  room: string;
  room_id: string;
  asset: string;
  title: string;
  instructions: string;
  due: string;
  status: 'assigned' | 'accepted' | 'verifying' | 'verified' | 'completed' | 'revoked' | 'rejected';
  is_complete: boolean;
  tasks: string[];
  checklist: ChecklistItem[];
  checkInAt: string | null;
  verifiedAt: string | null;
  tapAttempt: string | null;
}

export interface Device {
  device_hash: string;
  room_id: string;
}

export interface AuditEvent {
  id: string;
  timestamp: string;
  time?: string;
  device_ref: string;
  user_ref: string;
  message: string;
  text?: string;
  kind: 'info' | 'approved' | 'warning' | 'checkin' | 'task';
}

export interface AuthState {
  nfc_detected: boolean;
  otp_pending: boolean;
  authenticated: boolean;
  attempts_remaining: number;
  email_masked?: string;
  expires_in_sec?: number;
  email_notice?: string | null;
  magic_link_url?: string | null;
}

export interface TechnicianSummary {
  full_name: string;
  email: string;
  card_hash: string;
}

export interface TechnicianState {
  version: number;
  role: 'technician';
  technician: string;
  technician_card_hash: string;
  technician_email: string;
  rooms: string[];
  devices: Device[];
  tasks: TaskItem[];
  auth_state: AuthState;
  inbox: InboxMessage[];
}

export interface InboxMessage {
  attempt_id: string;
  to_name: string;
  to_email: string;
  subject: string;
  approval_url: string;
  expires_in_sec: number;
}

export interface SupervisorState {
  version: number;
  role: 'supervisor';
  supervisor: string;
  supervisor_card_hash: string;
  technician: string;
  rooms: string[];
  devices: Device[];
  technicians: TechnicianSummary[];
  tasks: TaskItem[];
  events: AuditEvent[];
  audit_log: AuditEvent[];
}

export interface JobMetadata {
  title: string;
  instructions: string;
  asset?: string;
  due?: string;
  room?: string;
}

export interface CreateJobData {
  title: string;
  room: string;
  asset: string;
  due: string;
  instructions: string;
  tasks: string[];
  [key: string]: unknown;
}

export const JOB_METADATA_STORAGE_KEY = 'permitproof_job_metadata';

export function getSavedJobMetadata(): Record<string, JobMetadata> {
  try {
    if (typeof window === 'undefined' || !window.localStorage) return {};
    const raw = window.localStorage.getItem(JOB_METADATA_STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

export function saveJobMetadata(jobId: string, meta: JobMetadata): void {
  try {
    if (typeof window === 'undefined' || !window.localStorage) return;
    const allMeta = getSavedJobMetadata();
    allMeta[jobId] = {
      ...(allMeta[jobId] || {}),
      ...meta,
    };
    window.localStorage.setItem(JOB_METADATA_STORAGE_KEY, JSON.stringify(allMeta));
  } catch (err) {
    console.error('Failed to save job metadata to localStorage', err);
  }
}

export function enrichTaskWithMetadata(task: TaskItem, metaMap?: Record<string, JobMetadata>): TaskItem {
  const meta = (metaMap || getSavedJobMetadata())[task.id];
  if (!meta) return task;
  return {
    ...task,
    title: meta.title && meta.title.trim() ? meta.title : task.title,
    instructions: meta.instructions && meta.instructions.trim() ? meta.instructions : task.instructions,
    asset: meta.asset && meta.asset.trim() ? meta.asset : task.asset,
    due: meta.due && meta.due.trim() ? meta.due : task.due,
  };
}

export function enrichTasks<T extends { tasks: TaskItem[] }>(state: T): T {
  if (!state || !Array.isArray(state.tasks)) return state;
  const metaMap = getSavedJobMetadata();
  return {
    ...state,
    tasks: state.tasks.map((task) => enrichTaskWithMetadata(task, metaMap)),
  };
}

export async function syncJobMetadataFromAuditLog(): Promise<Record<string, JobMetadata>> {
  try {
    if (typeof window === 'undefined' || !window.localStorage) return {};
    const res = await fetch('/api/v1/audit-events?event_type=JOB_CREATED&limit=100');
    if (!res.ok) return getSavedJobMetadata();
    const events: Array<{ metadata?: { job_id?: string; title?: string } }> = await res.json();
    const currentMeta = getSavedJobMetadata();
    let changed = false;
    for (const ev of events) {
      const jobId = ev.metadata?.job_id;
      const title = ev.metadata?.title;
      if (jobId && title) {
        if (!currentMeta[jobId]) {
          currentMeta[jobId] = { title, instructions: '' };
          changed = true;
        } else if (!currentMeta[jobId].title || currentMeta[jobId].title.startsWith('Zero-Trust Permit')) {
          currentMeta[jobId].title = title;
          changed = true;
        }
      }
    }
    if (changed) {
      window.localStorage.setItem(JOB_METADATA_STORAGE_KEY, JSON.stringify(currentMeta));
    }
    return currentMeta;
  } catch {
    return getSavedJobMetadata();
  }
}
