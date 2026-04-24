/**
 * ErrorView — LLD §3.1.3, Class: ErrorView
 * 
 * Displays error messages with retry and reset options.
 */

import { motion } from 'framer-motion';
import { AlertTriangle, RefreshCw, ArrowLeft } from 'lucide-react';
import { useEditorStore } from '../store/editorStore';

export default function ErrorView() {
    const { errorMessage, errorCode, clearError, resetSession, setCurrentView } =
        useEditorStore();

    return (
        <div className="flex items-center justify-center w-full h-full p-8">
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="flex flex-col items-center gap-6 p-8 rounded-2xl bg-red-500/10 border border-red-500/30 max-w-md w-full"
            >
                <AlertTriangle className="w-12 h-12 text-red-400" />

                <div className="text-center">
                    <h3 className="text-white text-lg font-semibold mb-2">
                        Something went wrong
                    </h3>
                    <p className="text-white/60 text-sm">
                        {errorMessage || 'An unexpected error occurred.'}
                    </p>
                    {errorCode && (
                        <p className="text-white/30 text-xs mt-1 font-mono">
                            Error: {errorCode}
                        </p>
                    )}
                </div>

                <div className="flex flex-col gap-2 w-full">
                    <motion.button
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={() => {
                            clearError();
                            setCurrentView('editing');
                        }}
                        className="flex items-center justify-center gap-2 p-3 rounded-xl bg-white/10 hover:bg-white/20 transition-all"
                    >
                        <ArrowLeft className="w-4 h-4 text-white/70" />
                        <span className="text-white/70 text-sm">Try Again</span>
                    </motion.button>

                    <motion.button
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={() => resetSession()}
                        className="flex items-center justify-center gap-2 p-3 rounded-xl bg-white/5 hover:bg-white/10 transition-all"
                    >
                        <RefreshCw className="w-4 h-4 text-white/50" />
                        <span className="text-white/50 text-sm">Start Over</span>
                    </motion.button>
                </div>
            </motion.div>
        </div>
    );
}
