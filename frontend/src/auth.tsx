import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { fetchMe, login as apiLogin, logout as apiLogout, getToken, type UserData } from './api';

// Defines the structure of our authentication context, holding user state and auth methods
interface AuthCtx {
    user: UserData | null;
    loading: boolean;
    login: (email: string, password: string) => Promise<void>;
    logout: () => void;
}


// Initialize the context with default empty values
const AuthContext = createContext<AuthCtx>({ user: null, loading: true, login: async () => {}, logout: () => {} });


/**
 * AuthProvider wraps the application to provide global access to user session state.
 * It automatically checks for an existing session on the first load.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<UserData | null>(null);

    const [loading, setLoading] = useState(true);

    // On initial mount, check if a token exists in storage. 
    // If it does, verify it with the backend and fetch the user's profile.
    useEffect(() => {
        if (getToken()) {

            fetchMe().then(setUser).catch(() => setUser(null)).finally(() => setLoading(false));
            
        } else {

            setLoading(false);
        }
    }, []);

    // Authenticates the user via the backend API and updates the local React state
    const login = async (email: string, password: string) => {
        const u = await apiLogin(email, password);
        setUser(u);
    };

    // Clears the user session and removes the token from local storage
    const logout = () => {
        apiLogout();

        setUser(null);
    };

    return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>;
}

/**
 * Custom hook to easily consume the authentication context in any component.
 * Example: const { user, logout } = useAuth();
 */
export function useAuth() {
    return useContext(AuthContext);
}
