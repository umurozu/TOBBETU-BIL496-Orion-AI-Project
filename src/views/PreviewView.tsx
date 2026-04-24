/**
 * PreviewView — LLD §3.1.3, Class: PreviewView
 * 
 * Displays the processed result with comparison toggle
 * and action buttons (download, re-edit, new image).
 */

import { motion } from 'framer-motion';
import { Download, Edit3, RefreshCw, Eye, Paintbrush } from 'lucide-react';
import { useEditorStore } from '../store/editorStore';

export default function PreviewView() {
    const {
        compareMode,
        setCompareMode,
        setCurrentView,
        resetSession,
    } = useEditorStore();

    return (
        <div className="flex flex-col gap-4 p-4 w-full">
            <h3 className="text-white/70 text-xs font-semibold uppercase tracking-wider mb-1">
                Preview
            </h3>

            {/* Comparison Toggle */}
            <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => setCompareMode(!compareMode)}
                className={`
          flex items-center gap-3 p-3 rounded-xl transition-all
          ${compareMode ? 'bg-purple-500/20 border border-purple-500/50' : 'bg-white/5 hover:bg-white/10 border border-transparent'}
        `}
            >
                <div className={`flex items-center justify-center w-10 h-10 rounded-lg ${compareMode ? 'bg-purple-500/30' : 'bg-white/10'}`}>
                    <Eye className="w-5 h-5 text-white/70" />
                </div>
                <div className="text-left">
                    <p className="text-white text-sm font-medium">Compare Mode</p>
                    <p className="text-white/40 text-xs">
                        {compareMode ? 'Showing comparison' : 'Click to compare'}
                    </p>
                </div>
            </motion.button>

            {/* Action Buttons */}
            <div className="flex flex-col gap-2 mt-2">
                <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => setCurrentView('download')}
                    className="flex items-center gap-3 p-3 rounded-xl bg-blue-500/20 hover:bg-blue-500/30 border border-blue-500/50 transition-all"
                >
                    <Download className="w-5 h-5 text-blue-400" />
                    <span className="text-white text-sm font-medium">Download Result</span>
                </motion.button>

                <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => setCurrentView('editing')}
                    className="flex items-center gap-3 p-3 rounded-xl bg-white/5 hover:bg-white/10 transition-all"
                >
                    <Edit3 className="w-5 h-5 text-white/70" />
                    <span className="text-white/70 text-sm">Apply Another Edit</span>
                </motion.button>

                <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => setCurrentView('refinement')}
                    className="flex items-center gap-3 p-3 rounded-xl bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/30 transition-all"
                >
                    <Paintbrush className="w-5 h-5 text-purple-400" />
                    <span className="text-purple-300 text-sm">Refine Mask</span>
                </motion.button>

                <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => resetSession()}
                    className="flex items-center gap-3 p-3 rounded-xl bg-white/5 hover:bg-white/10 transition-all"
                >
                    <RefreshCw className="w-5 h-5 text-white/70" />
                    <span className="text-white/70 text-sm">Upload New Image</span>
                </motion.button>
            </div>
        </div>
    );
}
