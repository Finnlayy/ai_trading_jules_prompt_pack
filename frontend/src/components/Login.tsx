import React from 'react';
import { GoogleOAuthProvider, GoogleLogin } from '@react-oauth/google';
import { useAuth } from '../context/AuthContext';

const Login: React.FC = () => {
    const { login } = useAuth();

    // In a real app, you would fetch the client ID from config/env
    const clientId = 'YOUR_GOOGLE_CLIENT_ID';

    return (
        <GoogleOAuthProvider clientId={clientId}>
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', backgroundColor: '#0a0a0a', color: '#fff' }}>
                <div style={{ padding: '2rem', backgroundColor: '#151618', borderRadius: '8px', textAlign: 'center' }}>
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
