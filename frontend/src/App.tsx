import React from 'react';
import { useAuth } from './context/AuthContext';
import Login from './components/Login';
import { ChartPanel } from './components/ChartPanel';
import { OrderTable } from './components/OrderTable';
import { WarRoom } from './components/WarRoom';
import { Ticker } from './components/Ticker';

const App: React.FC = () => {
    const { token, logout } = useAuth();

    if (!token) {
        return <Login />;
    }

    return (
        <div style={{ backgroundColor: '#0a0a0a', color: '#fff', minHeight: '100vh', fontFamily: 'monospace' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '1rem', borderBottom: '1px solid #333' }}>
                <h1>MetricFlow Command Center</h1>
                <button onClick={logout} style={{ padding: '8px', cursor: 'pointer' }}>Logout</button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1rem', padding: '1rem' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    <ChartPanel />
                    <OrderTable />
                </div>
                <div>
                    <WarRoom />
                </div>
            </div>

            <div style={{ position: 'fixed', bottom: 0, width: '100%' }}>
                <Ticker />
            </div>
        </div>
    );
};

export default App;
