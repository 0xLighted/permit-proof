import React from 'react';
import type { AuthState } from '../types';
import { Badge } from './Badge';

interface AuthPanelProps {
  authState: AuthState;
  technicianCardHash?: string;
  technicianName?: string;
}

export const AuthPanel: React.FC<AuthPanelProps> = ({ authState, technicianCardHash, technicianName }) => {
  const status = authState.authenticated ? 'verified' : authState.otp_pending ? 'verifying' : 'assigned';
  const label = authState.authenticated ? 'ACCESS APPROVED' : authState.otp_pending ? 'OWNER APPROVAL PENDING' : 'TAP REQUIRED';

  return (
    <div className="surface-card-lg" style={{ marginBottom: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '8px' }}>
        <div>
          <h2 className="section-header">Card Tap and Owner Approval</h2>
          <p className="micro-caption">PHYSICAL PI READER // SIGNED ACCESS REQUEST // ONE-TIME APPROVAL LINK</p>
        </div>
        <Badge status={status} label={label} />
      </div>

      {authState.authenticated ? (
        <div className="body-text">This physical card tap was approved. The Pi should show a blinking green indicator.</div>
      ) : authState.otp_pending ? (
        <div className="body-text">
          The Pi accepted a physical card tap and is waiting for owner approval. Open Inbox and follow the
          approval link within {authState.expires_in_sec ?? 120} seconds.
        </div>
      ) : (
        <div className="body-text">
          Accept the assigned job, then present the registered card once to the Raspberry Pi reader. Watch the Pi
          indicator and this page for the result.
        </div>
      )}

      {(technicianName || technicianCardHash) && (
        <div
          className="tech-code"
          style={{ color: 'var(--primary)', marginTop: '12px' }}
          title={technicianCardHash}
        >
          OPERATOR: {technicianName || (technicianCardHash ? `${technicianCardHash.slice(0, 8)}...` : '')}
        </div>
      )}
    </div>
  );
};
