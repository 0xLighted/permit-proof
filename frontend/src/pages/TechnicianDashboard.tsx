import React, { useState, useEffect, useCallback } from 'react';
import type { TechnicianState } from '../types';
import { fetchState, postAction } from '../api';
import { Shell } from '../components/Shell';
import { AuthPanel } from '../components/AuthPanel';
import { JobCard } from '../components/JobCard';

export const TechnicianDashboard: React.FC = () => {
  const [state, setState] = useState<TechnicianState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  const loadState = useCallback(async () => {
    try {
      const data = await fetchState<TechnicianState>();
      setState(data);
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
    return () => clearInterval(interval);
  }, [loadState]);

  const handleTapCard = async () => {
    if (!state || state.tasks.length === 0) {
      throw new Error('No assigned work orders available for NFC verification');
    }
    setIsProcessing(true);
    try {
      const activeTask = state.tasks.find((t) => t.status === 'assigned' || t.status === 'verifying') || state.tasks[0];
      const updated = await postAction<TechnicianState>('tap', { id: activeTask.id });
      setState(updated);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleVerifyOtp = async (otp: string) => {
    setIsProcessing(true);
    try {
      const updated = await postAction<TechnicianState>('verify_otp', { otp });
      setState(updated);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleToggleChecklist = async (taskId: string, index: number) => {
    setIsProcessing(true);
    try {
      const updated = await postAction<TechnicianState>('checklist', { id: taskId, index });
      setState(updated);
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
      setState(updated);
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
            onTapCard={handleTapCard}
            onVerifyOtp={handleVerifyOtp}
            isProcessing={isProcessing}
          />

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
                    isProcessing={isProcessing}
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
                    STATION SHA-256 HASH:
                  </div>
                  <div className="tech-code" style={{ fontSize: '11px', wordBreak: 'break-all' }}>
                    {device.device_hash}
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
