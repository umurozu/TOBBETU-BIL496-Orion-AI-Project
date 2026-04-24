/**
 * SessionExpiredView — LLD §3.1.3, Class: SessionExpiredView
 * 
 * Displayed when a session has expired.
 */

import { motion } from 'framer-motion';
import { Clock, RefreshCw } from 'lucide-react';
import { useEditorStore } from '../store/editorStore';

export default function SessionExpiredView() {
    const { resetSession } = useEditorStore();

    return (
        <div className="flex items-center justify-center w-full h-full p-8">
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="flex flex-col items-center gap-6 p-8 rounded-2xl bg-yellow-500/10 border border-yellow-500/30 max-w-md w-full"
            >
                <Clock className="w-12 h-12 text-yellow-400" />

                <div className="text-center">
                    <h3 className="text-white text-lg font-semibold mb-2">
                        Session Expired
                    </h3>
                    <p className="text-white/60 text-sm">
                        Your session has timed out. Image data has been cleared
                        for privacy. Please start a new session.
                    </p>
                </div>

                <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => resetSession()}
                    className="flex items-center justify-center gap-2 p-3 px-6 rounded-xl bg-gradient-to-r from-yellow-500 to-orange-500 hover:from-yellow-600 hover:to-orange-600 transition-all"
                >
                    <RefreshCw className="w-5 h-5 text-white" />
                    <span className="text-white text-sm font-semibold">Start New Session</span>
                </motion.button>
            </motion.div>
        </div>
    );
}
