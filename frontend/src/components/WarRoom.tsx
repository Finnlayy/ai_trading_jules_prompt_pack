import React from 'react';

export const WarRoom: React.FC = () => {
    return (
        <div style={{ padding: '1rem', backgroundColor: '#151618', borderRadius: '8px' }}>
            <h3>War Room Consensus</h3>
            <svg width="200" height="200">
                <circle cx="100" cy="100" r="40" fill="#3ebd93" />
                <text x="100" y="105" textAnchor="middle" fill="#000" fontSize="12">Consensus</text>
            </svg>
        </div>
    );
};
