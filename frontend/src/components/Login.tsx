import React, { useEffect, useState } from 'react';
import { GoogleOAuthProvider, GoogleLogin } from '@react-oauth/google';
import { useAuth } from '../context/AuthContext';

const Login: React.FC = () => {
    const { login } = useAuth();

    // The Google OAuth client ID is a public identifier fetched at runtime from
    // the backend (GET /api/auth/config), which reads it from GOOGLE_CLIENT_ID.
    // This avoids hardcoding it and rebuilding the SPA when the value changes.
    const [clientId, setClientId] = useState<string | null>(null);
    const [loading, setLoading] = useState<boolean>(true);

    useEffect(() => {
        fetch('/api/auth/config')
            .then(res => res.json())
            .then(data => setClientId(data.googleClientId || ''))
            .catch(() => setClientId(''))
            .finally(() => setLoading(false));
    }, []);

    const boxStyle: React.CSSProperties = {
        padding: '2rem',
        backgroundColor: '#151618',
        borderRadius: '8px',
        textAlign: 'center',
        maxWidth: '420px',
    };

    const containerStyle: React.CSSProperties = {
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
        backgroundColor: '#0a0a0a',
        color: '#fff',
    };

    if (loading) {
        return (
            <div style={containerStyle}>
                <div style={boxStyle}>
                    <h2 style={{ marginBottom: '1rem' }}>MetricFlow Command Center</h2>
                    <p style={{ color: '#8a8f98' }}>Loading sign-in…</p>
                </div>
            </div>
        );
    }

    if (!clientId) {
        return (
            <div style={containerStyle}>
                <div style={boxStyle}>
                    <h2 style={{ marginBottom: '1rem' }}>MetricFlow Command Center Login</h2>
                    <p style={{ color: '#e5484d' }}>
                        Google sign-in is not configured.
                    </p>
                    <p style={{ color: '#8a8f98', fontSize: '0.85rem' }}>
                        Set <code>GOOGLE_CLIENT_ID</code> in the backend environment
                        (a Google OAuth 2.0 Web Client ID ending in
                        <code>.apps.googleusercontent.com</code>) and reload.
                    </p>
                </div>
            </div>
        );
    }

    return (
        <GoogleOAuthProvider clientId={clientId}>
            <div style={containerStyle}>
                <div style={boxStyle}>
                    <h2 style={{ marginBottom: '2rem' }}>MetricFlow Command Center Login</h2>
                    <GoogleLogin
                        onSuccess={credentialResponse => {
                            if (credentialResponse.credential) {
                                // Send token to backend to get JWT
                                fetch('/api/auth/google', {
                                    method: 'POST',
                                    headers: {
                                        'Content-Type': 'application/json',
                                    },
                                    body: JSON.stringify({ token: credentialResponse.credential }),
                                })
                                .then(res => res.json())
                                .then(data => {
                                    if(data.access_token) {
                                        login(data.access_token);
                                    }
                                })
                                .catch(err => console.error(err));
                            }
                        }}
                        onError={() => {
                            console.log('Login Failed');
                        }}
                    />
                </div>
            </div>
        </GoogleOAuthProvider>
    );
};

export default Login;
