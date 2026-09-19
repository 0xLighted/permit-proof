import React from 'react';

interface ShellProps {
  currentRole: 'technician' | 'supervisor' | 'launcher';
  title: string;
  subtitle: string;
  children: React.ReactNode;
}

export const Shell: React.FC<ShellProps> = ({ currentRole, title, subtitle, children }) => {
  return (
    <div className="shell-container">
      <aside className="shell-sidebar">
        <div style={{ marginBottom: '2rem' }}>
          <div className="tech-code-primary" style={{ letterSpacing: '0.1em', marginBottom: '4px' }}>
            PERMITPROOF // V1.0
          </div>
          <div className="display-title" style={{ fontSize: '18px', lineHeight: '24px' }}>
            {currentRole === 'technician' ? 'Technician Station' : currentRole === 'supervisor' ? 'Supervisor Console' : 'Access Portal'}
          </div>
          <div className="micro-caption" style={{ marginTop: '4px' }}>
            INDUSTRIAL ACCESS & PERMIT VERIFICATION
          </div>
        </div>

        <nav style={{ display: 'flex', flexDirection: 'column', gap: '8px', flex: 1 }}>
          <div className="micro-caption" style={{ textTransform: 'uppercase', marginBottom: '4px' }}>
            Operational Nodes
          </div>
          <a
            href="http://localhost:1501/technician"
            className={currentRole === 'technician' ? 'btn-primary' : 'btn-secondary'}
            style={{ justifyContent: 'flex-start' }}
          >
            Technician Handheld (1501)
          </a>
          <a
            href="http://localhost:1502/supervisor"
            className={currentRole === 'supervisor' ? 'btn-primary' : 'btn-secondary'}
            style={{ justifyContent: 'flex-start' }}
          >
            Supervisor Console (1502)
          </a>
          <a
            href="http://localhost:1500/"
            className={currentRole === 'launcher' ? 'btn-primary' : 'btn-secondary'}
            style={{ justifyContent: 'flex-start' }}
          >
            Station Launcher (1500)
          </a>
        </nav>

        <div style={{ borderTop: '1px solid var(--border)', paddingTop: '1rem', marginTop: '1rem' }}>
          <div className="micro-caption">ENVIRONMENT</div>
          <div className="tech-code" style={{ color: 'var(--muted)', marginTop: '2px' }}>
            STANDALONE NODE // SHA-256 HMAC
          </div>
        </div>
      </aside>

      <main className="shell-content">
        <header style={{ marginBottom: '1.5rem', borderBottom: '1px solid var(--border)', paddingBottom: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <h1 className="display-title">{title}</h1>
              <p className="body-text" style={{ marginTop: '4px' }}>{subtitle}</p>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="badge-verified">
                <span className="indicator-square" />
                SYSTEM ONLINE
              </span>
            </div>
          </div>
        </header>

        {children}
      </main>
    </div>
  );
};
