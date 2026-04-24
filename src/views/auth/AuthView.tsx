import React, { useState } from 'react';
import { Mail, Lock, User, ArrowRight, Loader2, Sparkles } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { API_BASE_URL } from '../../services/api';

export const AuthView: React.FC = () => {
    const [isLogin, setIsLogin] = useState(true);
    const [email, setEmail] = useState('');
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [consentGiven, setConsentGiven] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);

    const setAuth = useAuthStore((state) => state.setAuth);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        setIsLoading(true);

        try {
            const endpoint = isLogin ? '/auth/login' : '/auth/register';
            const body = isLogin
                ? { email, password }
                : { email, username, password, consent_given: consentGiven };

            const res = await fetch(`${API_BASE_URL}${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });

            const data = await res.json();

            if (!res.ok) {
                // Professional error extraction: use message from APIResponse if available
                throw new Error(data.message || data.error?.message || 'Authentication failed');
            }

            // Standardize return based on endpoint:
            // Register returns { user, access_token, refresh_token }
            // Login returns { access_token, refresh_token } and we fetch user via /auth/me

            let userObj = data.data.user;
            let accessToken = data.data.access_token;
            let refreshToken = data.data.refresh_token;

            if (isLogin) {
                // Fetch user data via /auth/me
                const meRes = await fetch(`${API_BASE_URL}/auth/me`, {
                    headers: { Authorization: `Bearer ${accessToken}` },
                });
                const meData = await meRes.json();
                if (!meRes.ok) throw new Error("Failed to fetch user profile");
                userObj = meData.data;
            }

            setAuth(userObj, accessToken, refreshToken);
        } catch (err: any) {
            console.error('Auth error:', err);
            let msg = err.message || 'An unexpected error occurred';
            
            // Handle browser fetch failures specifically
            if (err instanceof TypeError && (err.message.includes('fetch') || err.message.includes('Failed'))) {
                msg = 'Cannot connect to server. The backend might be offline or still starting up. Please wait a moment and try again.';
            }
            
            setError(msg);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="flex h-screen w-full bg-slate-50 items-center justify-center p-4">
            <div className="w-full max-w-[440px] bg-white rounded-3xl p-8 shadow-2xl shadow-slate-200/50 border border-slate-100 relative overflow-hidden">
                {/* Background Decor */}
                <div className="absolute top-0 right-0 -mr-16 -mt-16 w-48 h-48 bg-blue-100 rounded-full blur-3xl opacity-50 pointer-events-none" />
                <div className="absolute bottom-0 left-0 -ml-16 -mb-16 w-48 h-48 bg-purple-100 rounded-full blur-3xl opacity-50 pointer-events-none" />

                <div className="relative z-10 flex flex-col items-center mb-8">
                    <div className="w-12 h-12 bg-gradient-to-tr from-blue-600 to-purple-600 rounded-xl flex items-center justify-center text-white mb-4 shadow-md">
                        <Sparkles size={24} fill="currentColor" />
                    </div>
                    <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                        Welcome to <span className="text-blue-600">Invisio</span>
                    </h1>
                    <p className="text-sm text-slate-500 mt-1 font-medium">
                        {isLogin ? 'Sign in to continue editing' : 'Create an account to get started'}
                    </p>
                </div>

                <form onSubmit={handleSubmit} className="relative z-10 space-y-4">
                    {/* Error Box */}
                    {error && (
                        <div className="bg-red-50 text-red-600 text-sm font-medium px-4 py-3 rounded-xl border border-red-100 text-center">
                            {error}
                        </div>
                    )}

                    {!isLogin && (
                        <div>
                            <label className="block text-[13px] font-bold text-slate-700 mb-1.5 px-1">Username</label>
                            <div className="relative">
                                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400">
                                    <User size={18} />
                                </div>
                                <input
                                    type="text"
                                    value={username}
                                    onChange={(e) => setUsername(e.target.value)}
                                    placeholder="johndoe"
                                    className="w-full bg-slate-50 border border-slate-200 text-slate-900 text-sm rounded-xl py-3 pl-11 pr-4 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all font-medium placeholder:text-slate-400"
                                    required={!isLogin}
                                />
                            </div>
                        </div>
                    )}

                    <div>
                        <label className="block text-[13px] font-bold text-slate-700 mb-1.5 px-1">Email Address</label>
                        <div className="relative">
                            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400">
                                <Mail size={18} />
                            </div>
                            <input
                                type="email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                placeholder="name@example.com"
                                className="w-full bg-slate-50 border border-slate-200 text-slate-900 text-sm rounded-xl py-3 pl-11 pr-4 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all font-medium placeholder:text-slate-400"
                                required
                            />
                        </div>
                    </div>

                    <div>
                        <div className="flex items-center justify-between mb-1.5 px-1">
                            <label className="block text-[13px] font-bold text-slate-700">Password</label>
                            {isLogin && (
                                <button type="button" className="text-[12px] font-bold text-blue-600 hover:text-blue-700">
                                    Forgot?
                                </button>
                            )}
                        </div>
                        <div className="relative">
                            <div className="relative inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400">
                                <Lock size={18} />
                            </div>
                            <input
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                placeholder="••••••••"
                                className="w-full bg-slate-50 border border-slate-200 text-slate-900 text-sm rounded-xl py-3 pl-11 pr-4 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all font-medium placeholder:text-slate-400"
                                required
                                minLength={6}
                            />
                        </div>
                    </div>

                    {!isLogin && (
                        <div className="flex items-start gap-3 px-1 py-1">
                            <input
                                type="checkbox"
                                id="consent"
                                checked={consentGiven}
                                onChange={(e) => setConsentGiven(e.target.checked)}
                                className="mt-1 w-4 h-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                                required
                            />
                            <label htmlFor="consent" className="text-[12px] text-slate-500 font-medium leading-relaxed cursor-pointer select-none">
                                I agree to the <button type="button" className="text-blue-600 hover:underline">Terms of Service</button> and <button type="button" className="text-blue-600 hover:underline">Privacy Policy</button>, and I consent to the processing of my personal data according to KVKK/GDPR.
                            </label>
                        </div>
                    )}

                    <button
                        type="submit"
                        disabled={isLoading}
                        className="w-full bg-gradient-to-r from-blue-600 to-purple-600 text-white font-bold text-sm py-3.5 rounded-xl hover:shadow-lg hover:shadow-blue-600/20 transition-all disabled:opacity-70 flex items-center justify-center gap-2 mt-2"
                    >
                        {isLoading ? (
                            <>
                                <Loader2 size={18} className="animate-spin" />
                                Processing...
                            </>
                        ) : (
                            <>
                                {isLogin ? 'Sign In' : 'Create Account'}
                                <ArrowRight size={18} />
                            </>
                        )}
                    </button>

                    <button
                        type="button"
                        onClick={() => {
                            setIsLogin(!isLogin);
                            setError(null);
                        }}
                        className="w-full text-center text-sm font-medium text-slate-500 hover:text-slate-800 transition-colors py-2"
                    >
                        {isLogin ? "Don't have an account? Sign up" : 'Already have an account? Sign in'}
                    </button>
                </form>
            </div>
        </div>
    );
};
