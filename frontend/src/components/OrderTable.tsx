import React from 'react';

export const OrderTable: React.FC = () => {
    return (
        <div style={{ padding: '1rem', backgroundColor: '#151618', borderRadius: '8px' }}>
            <h3>Orders</h3>
            <table style={{ width: '100%', color: '#fff', textAlign: 'left' }}>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Symbol</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>1</td>
                        <td>BTC/USDT</td>
                        <td>Pending</td>
                        <td>
                            <button style={{ marginRight: '8px', backgroundColor: '#3ebd93' }}>[Execute Now]</button>
                            <button style={{ backgroundColor: '#b84d4d' }}>[Veto]</button>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    );
};
