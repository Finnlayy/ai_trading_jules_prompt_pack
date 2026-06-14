import React from 'react';

export const Ticker: React.FC = () => {
    return (
        <div style={{
            backgroundColor: '#0a0a0a',
            color: '#3ebd93',
            padding: '8px',
            fontFamily: 'monospace',
            whiteSpace: 'nowrap',
            overflow: 'hidden'
        }}>
            <div style={{ animation: 'marquee 15s linear infinite' }}>
                Narrative Ticker: Simulated Trade Executed. Market conditions favorable.
            </div>
            <style>
                {`
                @keyframes marquee {
                    0%   { transform: translateX(100%); }
                    100% { transform: translateX(-100%); }
                }
                `}
            </style>
        </div>
    );
};
