import React, { createContext, useState, useContext } from 'react';

interface AuthContextType {
    token: string | null;
    login: (token: string) => void;
    logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{children: React.ReactNode}> = ({ children }) => {
    const [token, setToken] = useState<string | null>(localStorage.getItem('jwtToken'));

    const login = (newToken: string) => {
        setToken(newToken);
        localStorage.setItem('jwtToken', newToken);
    };

    const logout = () => {
        setToken(null);
        localStorage.removeItem('jwtToken');
    };

    return (
        <AuthContext.Provider value={{ token, login, logout }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};
