import React, { useState, useEffect } from 'react';
import { X, Cookie, ShieldCheck } from 'lucide-react';

export const CookieBanner: React.FC = () => {
    const [isVisible, setIsVisible] = useState(false);

    useEffect(() => {
        const consent = localStorage.getItem('cookie-consent');
        if (!consent) {
            const timer = setTimeout(() => setIsVisible(true), 1500);
            return () => clearTimeout(timer);
        }
    }, []);

    const handleAccept = () => {
        localStorage.setItem('cookie-consent', 'accepted');
        setIsVisible(false);
    };

    if (!isVisible) return null;

    return (
        <div className="fixed bottom-6 left-6 right-6 md:left-auto md:max-w-md z-[9999] animate-in fade-in slide-in-from-bottom-5 duration-500">
            <div className="bg-white/90 backdrop-blur-xl border border-slate-200/60 p-5 rounded-3xl shadow-2xl shadow-blue-900/10 flex flex-col gap-4">
                <div className="flex items-start justify-between gap-4">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-blue-50 rounded-xl flex items-center justify-center text-blue-600 shrink-0">
                            <Cookie size={20} />
                        </div>
                        <div>
                            <h3 className="text-[15px] font-bold text-slate-900">Cookie Consent</h3>
                            <p className="text-[12px] text-slate-500 font-medium leading-relaxed mt-0.5">
                                We use cookies to enhance your experience and analyze our traffic according to KVKK/GDPR policies.
                            </p>
                        </div>
                    </div>
                    <button 
                        onClick={() => setIsVisible(false)}
                        className="text-slate-400 hover:text-slate-600 transition-colors p-1"
                    >
                        <X size={18} />
                    </button>
                </div>

                <div className="flex items-center gap-3 mt-1">
                    <button
                        onClick={handleAccept}
                        className="flex-1 bg-slate-900 text-white text-[13px] font-bold py-2.5 rounded-xl hover:bg-slate-800 transition-all shadow-lg shadow-slate-900/10"
                    >
                        Accept All
                    </button>
                    <button
                        onClick={() => setIsVisible(false)}
                        className="flex-1 bg-slate-100 text-slate-700 text-[13px] font-bold py-2.5 rounded-xl hover:bg-slate-200 transition-all"
                    >
                        Decline
                    </button>
                </div>
                
                <div className="flex items-center gap-1.5 px-1">
                    <ShieldCheck size={14} className="text-emerald-500" />
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Secure & Compliant</span>
                </div>
            </div>
        </div>
    );
};
