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
  status: 'assigned' | 'verifying' | 'verified' | 'completed' | 'revoked' | 'rejected';
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
