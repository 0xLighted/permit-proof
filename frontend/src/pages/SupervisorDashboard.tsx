import React, { useState, useEffect, useCallback } from 'react';
import type { SupervisorState } from '../types';
import { fetchState, postAction } from '../api';
import { Shell } from '../components/Shell';
import { JobCard } from '../components/JobCard';
import { AuditLog } from '../components/AuditLog';
import { CreateJobDialog } from '../components/CreateJobDialog';

export const SupervisorDashboard: React.FC = () => {
  const [state, setState] = useState<SupervisorState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  const loadState = useCallback(async () => {
    try {
      const data = await fetchState<SupervisorState>();
      setState(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to connect to supervisor backend');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadState();
    const interval = setInterval(loadState, 3000);
    return () => clearInterval(interval);
  }, [loadState]);

  const handleCreateJob = async (jobData: {
    title: string;
    room: string;
    asset: string;
    due: string;
    instructions: string;
    tasks: string[];
  }) => {
    setIsProcessing(true);
    try {
      const updated = await postAction<SupervisorState>('create', jobData);
      setState(updated);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleRevokeJob = async (taskId: string) => {
    setIsProcessing(true);
    try {
      const updated = await postAction<SupervisorState>('revoke', { id: taskId });
      setState(updated);
    } catch (err: any) {
      setError(err.message || 'Revocation failed');
    } finally {
      setIsProcessing(false);
    }
  };

  if (loading && !state) {
    return (
      <Shell currentRole="supervisor" title="Supervisory Operations Console" subtitle="Connecting to central server...">
        <div className="surface-card">
          <div className="tech-code">LOADING OPERATIONAL TELEMETRY...</div>
        </div>
      </Shell>
    );
  }

  const activeCount = state?.tasks.filter((t) => ['assigned', 'verifying', 'verified'].includes(t.status)).length || 0;
  const completedCount = state?.tasks.filter((t) => t.is_complete).length || 0;
  const verifiedCount = state?.tasks.filter((t) => t.status === 'verified').length || 0;

  return (
    <Shell
      currentRole="supervisor"
      title="Supervisory Operations Console"
      subtitle={`Plant Supervisor: ${state?.supervisor || 'Chief Officer'} // Plant Authorization Level 4`}
    >
      {error && (
        <div style={{ border: '1px solid var(--border)', backgroundColor: 'var(--surface)', padding: '12px', borderRadius: 'var(--radius)', marginBottom: '1.5rem' }}>
          <div className="tech-code" style={{ color: '#F1F5F9' }}>[SYSTEM NOTICE] {error}</div>
        </div>
      )}

      {state && (
        <>
          {/* Top Operational Metrics */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
            <div className="surface-card">
              <div className="micro-caption">ACTIVE PERMITS</div>
              <div className="display-title" style={{ marginTop: '4px' }}>{activeCount}</div>
              <div className="tech-code-primary" style={{ marginTop: '2px' }}>DISPATCHED & IN FIELD</div>
            </div>
            <div className="surface-card">
              <div className="micro-caption">NFC VERIFIED SESSIONS</div>
              <div className="display-title" style={{ marginTop: '4px', color: 'var(--primary)' }}>{verifiedCount}</div>
              <div className="tech-code" style={{ color: 'var(--primary)', marginTop: '2px' }}>AUTHORIZED IN ROOM</div>
            </div>
            <div className="surface-card">
              <div className="micro-caption">COMPLETED WORK ORDERS</div>
              <div className="display-title" style={{ marginTop: '4px' }}>{completedCount}</div>
              <div className="tech-code" style={{ color: 'var(--muted)', marginTop: '2px' }}>COMMITTED TO LEDGER</div>
            </div>
            <div className="surface-card">
              <div className="micro-caption">REGISTERED STATIONS</div>
              <div className="display-title" style={{ marginTop: '4px' }}>{state.devices.length}</div>
              <div className="tech-code" style={{ color: 'var(--muted)', marginTop: '2px' }}>HARDWARE NODES</div>
            </div>
          </div>

          {/* Permit Management Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '8px' }}>
            <div>
              <h2 className="section-header">Permits & Work Orders</h2>
              <p className="micro-caption">CENTRAL AUTHORIZATION & REVOCATION REGISTRY</p>
            </div>
            <button
              type="button"
              className="btn-primary"
              onClick={() => setIsDialogOpen(true)}
            >
              + DISPATCH NEW PERMIT
            </button>
          </div>

          {/* Work Orders List */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '2rem' }}>
            {state.tasks.map((task) => (
              <JobCard
                key={task.id}
                task={task}
                role="supervisor"
                onRevoke={() => handleRevokeJob(task.id)}
                isProcessing={isProcessing}
              />
            ))}
          </div>

          {/* Audit Log Stream */}
          <div style={{ marginBottom: '2rem' }}>
            <AuditLog events={state.events || state.audit_log || []} />
          </div>

          {/* Create Job Dialog Modal */}
          <CreateJobDialog
            rooms={state.rooms}
            isOpen={isDialogOpen}
            onClose={() => setIsDialogOpen(false)}
            onSubmit={handleCreateJob}
            isProcessing={isProcessing}
          />
        </>
      )}
    </Shell>
  );
};
