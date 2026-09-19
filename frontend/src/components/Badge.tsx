import React from 'react';

interface BadgeProps {
  status: 'verified' | 'completed' | 'assigned' | 'verifying' | 'rejected' | 'revoked' | string;
  label?: string;
}

export const Badge: React.FC<BadgeProps> = ({ status, label }) => {
  const isVerified = status === 'verified' || status === 'completed';
  const displayLabel = label || status.toUpperCase();

  return (
    <span className={isVerified ? 'badge-verified' : 'badge-pending'}>
      <span className="indicator-square" />
      {displayLabel}
    </span>
  );
};
