import React, { useState, useEffect, useCallback } from 'react';
import type { TechnicianState } from '../types';
import {
  enrichTasks,
  syncJobMetadataFromAuditLog,
  JOB_METADATA_STORAGE_KEY,
} from '../types';
import { fetchState, postAction } from '../api';
import { Shell } from '../components/Shell';
import { AuthPanel } from '../components/AuthPanel';
import { JobCard } from '../components/JobCard';
import { Badge } from '../components/Badge';

export const TechnicianDashboard: React.FC = () => {
  const [state, setState] = useState<TechnicianState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  // Track job IDs where accept has been clicked but poll hasn't refreshed status yet
  const pendingAccepts = React.useRef<Set<string>>(new Set());

  const loadState = useCallback(async () => {
    try {
      await syncJobMetadataFromAuditLog();
      const data = await fetchState<TechnicianState>('technician');
      // Clear pending accepts for jobs that have moved past 'assigned'
      data.tasks.forEach((t) => {
        if (t.status !== 'assigned') pendingAccepts.current.delete(t.id);
      });
      setState(enrichTasks(data));
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to connect to station API');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadState();
    const interval = setInterval(loadState, 3000);
    const handleStorage = (e: StorageEvent) => {
      if (e.key === JOB_METADATA_STORAGE_KEY) {
        setState((prev) => (prev ? enrichTasks(prev) : prev));
      }
    };
    window.addEventListener('storage', handleStorage);
    return () => {
      clearInterval(interval);
      window.removeEventListener('storage', handleStorage);
    };
  }, [loadState]);

  const handleAcceptJob = async (taskId: string) => {
    if (pendingAccepts.current.has(taskId)) return; // prevent double-click spam
    pendingAccepts.current.add(taskId);
    setIsProcessing(true);
    try {
      const updated = await postAction<TechnicianState>('accept', { id: taskId });
      setState(enrichTasks(updated));
    } catch (err: any) {
      pendingAccepts.current.delete(taskId); // restore if failed
      setError(err.message || 'Failed to accept work order');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSkipJob = async (taskId: string) => {
    setIsProcessing(true);
    try {
      const updated = await postAction<TechnicianState>('skip', { id: taskId });
      setState(enrichTasks(updated));
    } catch (err: any) {
      setError(err.message || 'Failed to skip work order');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleToggleChecklist = async (taskId: string, index: number) => {
    setIsProcessing(true);
    try {
      const updated = await postAction<TechnicianState>('checklist', { id: taskId, index });
      setState(enrichTasks(updated));
    } catch (err: any) {
      setError(err.message || 'Checklist update failed');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleCompleteTask = async (taskId: string) => {
    setIsProcessing(true);
    try {
      const updated = await postAction<TechnicianState>('complete', { id: taskId });
      setState(enrichTasks(updated));
    } catch (err: any) {
      setError(err.message || 'Task completion failed');
    } finally {
      setIsProcessing(false);
    }
  };

  if (loading && !state) {
    return (
      <Shell currentRole="technician" title="Field Technician Handheld" subtitle="Connecting to station hardware...">
        <div className="surface-card">
          <div className="tech-code">INITIALIZING SECURE STATION CONNECTION...</div>
        </div>
      </Shell>
    );
  }

  return (
    <Shell
      currentRole="technician"
      title="Field Technician Handheld"
      subtitle={`Authenticated Operator: ${state?.technician || 'Field Specialist'} // Zone Telemetry Active`}
    >
      {error && (
        <div style={{ border: '1px solid var(--border)', backgroundColor: 'var(--surface)', padding: '12px', borderRadius: 'var(--radius)', marginBottom: '1.5rem' }}>
          <div className="tech-code" style={{ color: '#F1F5F9' }}>[SYSTEM NOTICE] {error}</div>
        </div>
      )}

      {state && (
        <>
          {/* Two-factor authentication module */}
          <AuthPanel
            authState={state.auth_state}
            technicianCardHash={state.technician_card_hash}
            technicianName={state.technician}
          />

          <section id="inbox" className="surface-card-lg" style={{ marginBottom: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '8px' }}>
              <div>
                <h2 className="section-header">Approval Inbox</h2>
                <p className="micro-caption">OUT-OF-BAND CHALLENGE VERIFICATION</p>
              </div>
              <Badge
                status={state.inbox.length > 0 ? 'verifying' : 'assigned'}
                label={state.inbox.length > 0 ? `${state.inbox.length} PENDING LINK` : '0 PENDING'}
              />
            </div>

            {state.inbox.length === 0 ? (
              <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '1.25rem', backgroundColor: 'var(--bg)' }}>
                <p className="body-text" style={{ margin: 0 }}>
                  No pending access requests. Once your physical badge is detected by the station reader, a cryptographic single-use approval message will appear here.
                </p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {state.inbox.map((message) => (
                  <div
                    key={message.attempt_id}
                    style={{
                      border: '1px solid var(--border)',
                      borderRadius: 'var(--radius)',
                      backgroundColor: 'var(--bg)',
                      padding: '1.25rem',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.75rem',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '8px' }}>
                      <div>
                        <div className="card-title" style={{ color: 'var(--text)' }}>
                          {message.subject}
                        </div>
                        <div className="micro-caption" style={{ marginTop: '2px' }}>
                          RECIPIENT: {message.to_name} &lt;{message.to_email}&gt;
                        </div>
                      </div>
                      <span className="badge-pending">
                        <span className="indicator-square" style={{ backgroundColor: 'var(--primary)' }} />
                        <span className="tech-code-primary" style={{ fontSize: '11px' }}>
                          {message.expires_in_sec}S VALID
                        </span>
                      </span>
                    </div>

                    <p className="body-text" style={{ fontSize: '13px', lineHeight: '20px' }}>
                      Card tap recognized at the reader station. Confirm and authorize this request to immediately release the fail-closed lock mechanism.
                    </p>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px', paddingTop: '0.5rem', borderTop: '1px solid var(--border)' }}>
                      <span className="tech-code" style={{ fontSize: '11px', color: 'var(--muted)' }}>
                        ATTEMPT: {message.attempt_id.slice(0, 8)}...
                      </span>
                      <a
                        className="btn-primary"
                        href={message.approval_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ minHeight: '36px', padding: '6px 14px', fontSize: '13px' }}
                      >
                        APPROVE ACCESS LINK ↗
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Assigned Work Orders */}
          <div style={{ marginBottom: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <div>
                <h2 className="section-header">Assigned Permits & Work Orders</h2>
                <p className="micro-caption">MANDATORY SAFE PROTOCOL ADHERENCE</p>
              </div>
              <div className="tech-code" style={{ color: 'var(--muted)' }}>
                {state.tasks.length} PERMITS ON FILE
              </div>
            </div>

            {state.tasks.length === 0 ? (
              <div className="surface-card">
                <div className="body-text" style={{ textAlign: 'center', padding: '2rem' }}>
                  No active work orders dispatched to your technician badge hash.
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {state.tasks.map((task) => (
                  <JobCard
                    key={task.id}
                    task={task}
                    role="technician"
                    isAuthenticated={state.auth_state.authenticated}
                    onToggleChecklist={(idx) => handleToggleChecklist(task.id, idx)}
                    onComplete={() => handleCompleteTask(task.id)}
                    onAccept={() => handleAcceptJob(task.id)}
                    onSkip={() => handleSkipJob(task.id)}
                    isProcessing={isProcessing || pendingAccepts.current.has(task.id)}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Registered Hardware Station Telemetry */}
          <div className="surface-card">
            <h3 className="card-title" style={{ marginBottom: '4px' }}>Registered Hardware Station</h3>
            <p className="micro-caption" style={{ marginBottom: '12px' }}>
              HARDWARE WHITEBOARD SPECIFICATION // CRYPTOGRAPHIC ENDPOINTS
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '12px' }}>
              {state.devices.map((device, idx) => (
                <div key={idx} style={{ border: '1px solid var(--border)', padding: '10px 12px', borderRadius: 'var(--radius)' }}>
                  <div className="tech-code-primary" style={{ marginBottom: '2px' }}>{device.room_id}</div>
                  <div className="tech-code" style={{ fontSize: '11px', color: 'var(--muted)' }}>
                    NFC READER ONLINE
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </Shell>
  );
};
