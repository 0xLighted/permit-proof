import React from 'react';
import { Shell } from '../components/Shell';

export const LauncherPage: React.FC = () => {
  return (
    <Shell
      currentRole="launcher"
      title="PermitProof Operational Portal"
      subtitle="Dual-Factor Field Permit & Physical Access Verification System"
    >
      <div className="surface-card-lg" style={{ marginBottom: '2rem' }}>
        <div className="tech-code-primary" style={{ marginBottom: '8px' }}>
          INDUSTRIAL IoT SECURITY FRAMEWORK // ISO/IEC 27001 ADAPTATION
        </div>
        <h2 className="display-title" style={{ fontSize: '20px', marginBottom: '8px' }}>
          Mission-Critical Access & Work Order Verification
        </h2>
        <p className="body-text" style={{ maxWidth: '800px', marginBottom: '1.5rem' }}>
          PermitProof enforces fail-safe, cryptographic validation of field personnel prior to physical plant
          access or machinery maintenance. Factor 1 requires physical proximity via NFC hardware badges;
          Factor 2 confirms operator identity via time-bound, out-of-band email one-time passcodes.
        </p>

        <div className="grid-two">
          <div className="surface-card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div>
              <div className="tech-code-primary" style={{ marginBottom: '4px' }}>PORT 1501 // HANDHELD</div>
              <h3 className="section-header">Field Technician Terminal</h3>
              <p className="body-text" style={{ marginTop: '4px' }}>
                Used by on-site technicians to verify room access badges, authenticate via OTP, inspect assigned
                procedure checklists, and commit signed maintenance records.
              </p>
            </div>
            <div style={{ marginTop: 'auto' }}>
              <a href="http://localhost:1501/technician" className="btn-primary" style={{ width: '100%' }}>
                LAUNCH TECHNICIAN TERMINAL →
              </a>
            </div>
          </div>

          <div className="surface-card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div>
              <div className="tech-code-primary" style={{ marginBottom: '4px' }}>PORT 1502 // CONSOLE</div>
              <h3 className="section-header">Plant Supervisor Station</h3>
              <p className="body-text" style={{ marginTop: '4px' }}>
                Used by engineering supervisors and compliance officers to dispatch work orders, monitor active
                verification sessions, review cryptographic audit streams, and revoke permits.
              </p>
            </div>
            <div style={{ marginTop: 'auto' }}>
              <a href="http://localhost:1502/supervisor" className="btn-primary" style={{ width: '100%' }}>
                LAUNCH SUPERVISOR CONSOLE →
              </a>
            </div>
          </div>
        </div>
      </div>

      <div className="surface-card">
        <h3 className="card-title" style={{ marginBottom: '6px' }}>Zero-Trust Cryptographic Principles</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1rem', marginTop: '1rem' }}>
          <div style={{ border: '1px solid var(--border)', padding: '12px', borderRadius: 'var(--radius)' }}>
            <div className="tech-code" style={{ color: 'var(--primary)', marginBottom: '4px' }}>
              1. NO SENSITIVE IDENTIFIERS
            </div>
            <div className="body-text" style={{ fontSize: '13px' }}>
              Physical NFC UIDs and hardware MAC addresses are strictly converted to SHA-256 digests prior to persistence.
            </div>
          </div>
          <div style={{ border: '1px solid var(--border)', padding: '12px', borderRadius: 'var(--radius)' }}>
            <div className="tech-code" style={{ color: 'var(--primary)', marginBottom: '4px' }}>
              2. TIME-BOUND HMAC CHALLENGE
            </div>
            <div className="body-text" style={{ fontSize: '13px' }}>
              Hardware station handshakes enforce 10-second nonces with SHA-256 HMAC digest validation.
            </div>
          </div>
          <div style={{ border: '1px solid var(--border)', padding: '12px', borderRadius: 'var(--radius)' }}>
            <div className="tech-code" style={{ color: 'var(--primary)', marginBottom: '4px' }}>
              3. STRICT ROLE-BASED ISOLATION
            </div>
            <div className="body-text" style={{ fontSize: '13px' }}>
              Technicians only view and interact with assigned tasks; supervisors retain single-authority revocation.
            </div>
          </div>
        </div>
      </div>
    </Shell>
  );
};
