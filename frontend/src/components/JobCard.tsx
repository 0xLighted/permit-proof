import React from 'react';
import type { TaskItem } from '../types';
import { Badge } from './Badge';

interface JobCardProps {
  task: TaskItem;
  role: 'technician' | 'supervisor';
  isAuthenticated?: boolean;
  onToggleChecklist?: (index: number) => void;
  onComplete?: () => void;
  onRevoke?: () => void;
  onAccept?: () => void;
  onSkip?: () => void;
  isProcessing?: boolean;
}

export const JobCard: React.FC<JobCardProps> = ({
  task,
  role,
  isAuthenticated,
  onToggleChecklist,
  onComplete,
  onRevoke,
  onAccept,
  onSkip,
  isProcessing,
}) => {
  const allTasksDone = task.checklist.length > 0 && task.checklist.every((c) => c.done);
  const canInteract = role === 'technician' && (task.status === 'verified' || isAuthenticated);

  return (
    <div className="surface-card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '8px' }}>
        <div>
          <h3 className="card-title" style={{ fontSize: '16px' }}>{task.title}</h3>
          <div className="micro-caption" style={{ marginTop: '2px' }}>
            LOCATION: {task.room} | DUE: {task.due}
          </div>
        </div>
        <Badge status={task.status} />
      </div>

      {/* Instructions */}
      <div style={{ borderLeft: '2px solid var(--border)', paddingLeft: '10px' }}>
        <div className="micro-caption" style={{ marginBottom: '2px' }}>OPERATIONAL INSTRUCTIONS</div>
        <div className="body-text">{task.instructions}</div>
      </div>

      {/* Checklist */}
      <div>
        <div className="micro-caption" style={{ marginBottom: '6px', textTransform: 'uppercase' }}>
          Procedure Checklist ({task.checklist.filter((c) => c.done).length}/{task.checklist.length})
        </div>
        <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '0 12px' }}>
          {task.checklist.map((item, idx) => (
            <div key={idx} className="checklist-item">
              <input
                type="checkbox"
                id={`check-${task.id}-${idx}`}
                checked={item.done}
                disabled={!canInteract || isProcessing || task.is_complete}
                onChange={() => onToggleChecklist && onToggleChecklist(idx)}
                className="checkbox-custom"
              />
              <label
                htmlFor={`check-${task.id}-${idx}`}
                className="body-text"
                style={{
                  color: item.done ? 'var(--primary)' : 'var(--text)',
                  cursor: canInteract && !task.is_complete ? 'pointer' : 'default',
                  textDecoration: item.done ? 'line-through' : 'none',
                }}
              >
                {item.label}
              </label>
            </div>
          ))}
        </div>
      </div>

      {/* Role Actions */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 'auto', paddingTop: '8px', borderTop: '1px solid var(--border)', flexWrap: 'wrap', gap: '8px' }}>
        {task.status !== 'assigned' && (
          <div className="tech-code" style={{ fontSize: '11px', color: 'var(--muted)' }}>
            ASSIGNED TECH: {task.technician}
          </div>
        )}

        {role === 'technician' && task.status === 'assigned' && onAccept && (
          <div style={{ display: 'flex', gap: '8px' }}>
            {onSkip && (
              <button
                type="button"
                className="btn-secondary"
                disabled={isProcessing}
                onClick={onSkip}
                style={{ minHeight: '36px', padding: '4px 12px', fontSize: '12px' }}
              >
                SKIP
              </button>
            )}
            <button
              type="button"
              className="btn-primary"
              disabled={isProcessing}
              onClick={() => { onAccept && onAccept(); }}
              style={{ minHeight: '36px', padding: '4px 12px', fontSize: '12px' }}
            >
              {isProcessing ? 'ACCEPTING...' : 'ACCEPT WORK ORDER'}
            </button>
          </div>
        )}

        {role === 'technician' && task.status === 'accepted' && (
          <div className="tech-code" style={{ color: 'var(--primary)', fontSize: '12px' }}>
            WORK ORDER ACCEPTED. TAP YOUR CARD AT THE PHYSICAL PI READER.
          </div>
        )}

        {role === 'technician' && task.status === 'verified' && !task.is_complete && (
          <button
            type="button"
            className="btn-primary"
            disabled={!allTasksDone || isProcessing}
            onClick={onComplete}
            style={{ minHeight: '40px', padding: '6px 14px' }}
          >
            {isProcessing ? 'COMMITTING...' : 'SUBMIT FINDINGS'}
          </button>
        )}

        {role === 'supervisor' && ['assigned', 'accepted', 'verifying', 'verified'].includes(task.status) && (
          <button
            type="button"
            className="btn-secondary"
            disabled={isProcessing}
            onClick={onRevoke}
            style={{ minHeight: '40px', padding: '6px 14px' }}
          >
            REVOKE PERMIT
          </button>
        )}
      </div>
    </div>
  );
};
