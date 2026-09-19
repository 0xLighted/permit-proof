import React, { useState } from 'react';
import type { AuthState } from '../types';
import { Badge } from './Badge';

interface AuthPanelProps {
  authState: AuthState;
  taskId?: string;
  technicianCardHash?: string;
  onTapCard: () => Promise<void>;
  onVerifyOtp: (otp: string) => Promise<void>;
  isProcessing: boolean;
}

export const AuthPanel: React.FC<AuthPanelProps> = ({
  authState,
  technicianCardHash,
  onTapCard,
  onVerifyOtp,
  isProcessing,
}) => {
  const [otpInput, setOtpInput] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleOtpSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!otpInput.trim()) return;
    setErrorMessage(null);
    try {
      await onVerifyOtp(otpInput.trim());
      setOtpInput('');
    } catch (err: any) {
      setErrorMessage(err.message || 'OTP verification failed');
    }
  };

  const handleTap = async () => {
    setErrorMessage(null);
    try {
      await onTapCard();
    } catch (err: any) {
      setErrorMessage(err.message || 'NFC detection failed');
    }
  };

  return (
    <div className="surface-card-lg" style={{ marginBottom: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '8px' }}>
        <div>
          <h2 className="section-header">Two-Factor Identity Verification</h2>
          <p className="micro-caption">FACTOR 1: PHYSICAL NFC BADGE // FACTOR 2: TIME-BOUND OTP</p>
        </div>
        <Badge
          status={authState.authenticated ? 'verified' : authState.otp_pending ? 'verifying' : 'assigned'}
          label={authState.authenticated ? 'SESSION ACTIVE' : authState.otp_pending ? '2FA PENDING' : 'AUTH REQUIRED'}
        />
      </div>

      {errorMessage && (
        <div
          style={{
            border: '1px solid var(--border)',
            backgroundColor: 'var(--bg)',
            padding: '10px 12px',
            borderRadius: 'var(--radius)',
            marginBottom: '1rem',
          }}
        >
          <div className="tech-code" style={{ color: '#F1F5F9' }}>
            [SECURITY ALERT] {errorMessage}
          </div>
        </div>
      )}

      {authState.email_notice && (
        <div
          style={{
            border: '1px solid var(--primary)',
            backgroundColor: 'var(--bg)',
            padding: '10px 12px',
            borderRadius: 'var(--radius)',
            marginBottom: '1rem',
          }}
        >
          <div className="micro-caption" style={{ color: 'var(--primary)', marginBottom: '2px' }}>
            DISPATCH GATEWAY (LOCAL DEMO STREAM)
          </div>
          <div className="tech-code-primary">
            {authState.email_notice}
          </div>
        </div>
      )}

      {/* Authenticated State */}
      {authState.authenticated ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div className="body-text">
            Technician identity validated via dual-factor hardware challenge. Permit authorized for active work orders.
          </div>
          {technicianCardHash && (
            <div className="tech-code" style={{ color: 'var(--primary)', marginTop: '4px' }}>
              OPERATOR CARD HASH: {technicianCardHash}
            </div>
          )}
        </div>
      ) : (
        <div className="grid-two">
          {/* Factor 1: NFC Card */}
          <div style={{ border: '1px solid var(--border)', padding: '1rem', borderRadius: 'var(--radius)' }}>
            <div className="card-title" style={{ marginBottom: '4px' }}>Factor 1: NFC Field Badge</div>
            <p className="body-text" style={{ fontSize: '12px', marginBottom: '12px' }}>
              Present authorized technician badge to the hardware station reader.
            </p>
            <button
              type="button"
              className="btn-primary"
              onClick={handleTap}
              disabled={isProcessing || authState.otp_pending}
              style={{ width: '100%' }}
            >
              {isProcessing ? 'SCANNING NFC...' : authState.otp_pending ? 'NFC BADGE VERIFIED' : 'SIMULATE NFC TAP'}
            </button>
          </div>

          {/* Factor 2: Email OTP */}
          <div style={{ border: '1px solid var(--border)', padding: '1rem', borderRadius: 'var(--radius)' }}>
            <div className="card-title" style={{ marginBottom: '4px' }}>Factor 2: Out-of-Band OTP</div>
            <p className="body-text" style={{ fontSize: '12px', marginBottom: '8px' }}>
              Enter 6-digit code dispatched to registered address ({authState.email_masked || 'registered email'}).
            </p>
            <form onSubmit={handleOtpSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <input
                type="text"
                maxLength={6}
                placeholder="6-digit OTP"
                value={otpInput}
                onChange={(e) => setOtpInput(e.target.value)}
                disabled={!authState.otp_pending || isProcessing}
                className="form-input form-input-mono"
                style={{ textAlign: 'center', fontSize: '18px', letterSpacing: '0.2em' }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="micro-caption">
                  ATTEMPTS REMAINING: {authState.attempts_remaining}
                </span>
                <button
                  type="submit"
                  className="btn-secondary"
                  disabled={!authState.otp_pending || isProcessing || !otpInput.trim()}
                  style={{ minHeight: '40px', padding: '6px 14px' }}
                >
                  VERIFY OTP
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
