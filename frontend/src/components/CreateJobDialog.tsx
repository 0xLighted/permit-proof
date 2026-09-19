import React, { useState } from 'react';

interface CreateJobDialogProps {
  rooms: string[];
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (jobData: {
    title: string;
    room: string;
    asset: string;
    due: string;
    instructions: string;
    tasks: string[];
  }) => Promise<void>;
  isProcessing: boolean;
}

export const CreateJobDialog: React.FC<CreateJobDialogProps> = ({
  rooms,
  isOpen,
  onClose,
  onSubmit,
  isProcessing,
}) => {
  const [title, setTitle] = useState('');
  const [room, setRoom] = useState(rooms[0] || 'Server Room B');
  const [asset, setAsset] = useState('');
  const [due, setDue] = useState('2026-09-20T18:00');
  const [instructions, setInstructions] = useState('');
  const [tasksRaw, setTasksRaw] = useState(
    'Inspect assigned asset equipment\nRecord operating parameters\nSubmit maintenance evidence'
  );
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !asset.trim() || !instructions.trim()) {
      setError('Please complete all required fields.');
      return;
    }
    setError(null);
    const tasks = tasksRaw
      .split('\n')
      .map((t) => t.trim())
      .filter((t) => t.length > 0);

    try {
      await onSubmit({
        title: title.trim(),
        room,
        asset: asset.trim(),
        due,
        instructions: instructions.trim(),
        tasks: tasks.length > 0 ? tasks : ['Inspect asset', 'Verify status'],
      });
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to dispatch job');
    }
  };

  return (
    <div className="modal-backdrop">
      <div className="modal-dialog">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
          <div>
            <h2 className="section-header">Dispatch Maintenance Work Order</h2>
            <p className="micro-caption">CREATE AUTHORIZED FIELD PERMIT</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="btn-secondary"
            style={{ minHeight: '32px', padding: '4px 10px', fontSize: '12px' }}
          >
            ✕
          </button>
        </div>

        {error && (
          <div style={{ border: '1px solid var(--border)', padding: '8px 12px', marginBottom: '1rem', borderRadius: 'var(--radius)' }}>
            <div className="tech-code" style={{ color: '#F1F5F9' }}>{error}</div>
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div>
            <label className="form-label">Job Title / Summary</label>
            <input
              type="text"
              className="form-input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Inspect chiller compressor pressure"
              required
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div>
              <label className="form-label">Zone / Room Location</label>
              <select
                className="form-input"
                value={room}
                onChange={(e) => setRoom(e.target.value)}
              >
                {rooms.map((r) => (
                  <option key={r} value={r} style={{ backgroundColor: 'var(--surface)', color: 'var(--text)' }}>
                    {r}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="form-label">Asset Identifier</label>
              <input
                type="text"
                className="form-input"
                value={asset}
                onChange={(e) => setAsset(e.target.value)}
                placeholder="e.g. HVAC-CH-02"
                required
              />
            </div>
          </div>

          <div>
            <label className="form-label">Target Completion (Due Date/Time)</label>
            <input
              type="text"
              className="form-input"
              value={due}
              onChange={(e) => setDue(e.target.value)}
              placeholder="2026-09-20T18:00"
            />
          </div>

          <div>
            <label className="form-label">Operational Instructions</label>
            <textarea
              className="form-input"
              rows={3}
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder="Provide exact safety and maintenance instructions..."
              style={{ resize: 'vertical' }}
              required
            />
          </div>

          <div>
            <label className="form-label">Procedure Checklist Items (one per line)</label>
            <textarea
              className="form-input form-input-mono"
              rows={3}
              value={tasksRaw}
              onChange={(e) => setTasksRaw(e.target.value)}
              style={{ resize: 'vertical', fontSize: '12px' }}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '0.5rem' }}>
            <button
              type="button"
              className="btn-secondary"
              onClick={onClose}
              disabled={isProcessing}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn-primary"
              disabled={isProcessing}
            >
              {isProcessing ? 'Dispatching...' : 'Authorize & Dispatch'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
