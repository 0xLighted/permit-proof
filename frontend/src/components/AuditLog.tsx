import React from 'react';
import type { AuditEvent } from '../types';

interface AuditLogProps {
  events: AuditEvent[];
}

export const AuditLog: React.FC<AuditLogProps> = ({ events }) => {
  return (
    <div className="surface-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <div>
          <h2 className="section-header">Cryptographic Audit Stream</h2>
          <p className="micro-caption">TAMPER-EVIDENT JSON TELEMETRY LOG // SHA-256 IDENTIFIERS</p>
        </div>
        <div className="tech-code" style={{ color: 'var(--muted)' }}>
          {events.length} EVENTS RECORDED
        </div>
      </div>

      <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)', backgroundColor: 'var(--bg)' }}>
              <th className="micro-caption" style={{ padding: '10px 12px' }}>TIMESTAMP</th>
              <th className="micro-caption" style={{ padding: '10px 12px' }}>EVENT AUDIT RECORD</th>
              <th className="micro-caption" style={{ padding: '10px 12px' }}>DEVICE HASH REF</th>
              <th className="micro-caption" style={{ padding: '10px 12px' }}>USER HASH REF</th>
            </tr>
          </thead>
          <tbody>
            {events.length === 0 ? (
              <tr>
                <td colSpan={4} className="body-text" style={{ padding: '2rem', textAlign: 'center' }}>
                  No audit events recorded in current ledger.
                </td>
              </tr>
            ) : (
              events.map((evt) => {
                const isApproved = evt.kind === 'approved';
                return (
                  <tr key={evt.id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td className="tech-code" style={{ padding: '10px 12px', whiteSpace: 'nowrap', color: 'var(--muted)' }}>
                      {new Date(evt.timestamp).toLocaleTimeString()}
                    </td>
                    <td className="body-text" style={{ padding: '10px 12px', color: isApproved ? 'var(--primary)' : 'var(--text)' }}>
                      {evt.message || evt.text}
                    </td>
                    <td className="tech-code" style={{ padding: '10px 12px', whiteSpace: 'nowrap', color: 'var(--muted)' }}>
                      {evt.device_ref ? `${evt.device_ref.slice(0, 8)}...` : 'N/A'}
                    </td>
                    <td className="tech-code" style={{ padding: '10px 12px', whiteSpace: 'nowrap', color: 'var(--muted)' }}>
                      {evt.user_ref ? `${evt.user_ref.slice(0, 8)}...` : 'N/A'}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
