import React from 'react';
import { motion } from 'framer-motion';

/**
 * ScanningOverlay — Provides a "terminator style" scanning beam 
 * that traverses the image while processing is active.
 */
export const ScanningOverlay: React.FC = () => {
    return (
        <div className="absolute inset-0 z-20 pointer-events-none overflow-hidden rounded-lg">
            {/* Scanning Beam (Left to Right) */}
            <motion.div
                initial={{ left: '-10%' }}
                animate={{ left: '110%' }}
                transition={{
                    duration: 2.5,
                    repeat: Infinity,
                    ease: "linear"
                }}
                className="absolute top-0 bottom-0 w-24 z-20"
                style={{
                    background: 'linear-gradient(to right, transparent, rgba(59, 130, 246, 0.4), rgba(59, 130, 246, 0.6), rgba(59, 130, 246, 0.4), transparent)',
                    filter: 'blur(8px)',
                    boxShadow: '0 0 40px 10px rgba(59, 130, 246, 0.3)',
                }}
            >
                {/* Bright core line */}
                <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 w-[2px] bg-blue-400 opacity-80" />
            </motion.div>

            {/* Subtle pulse overlay */}
            <motion.div 
                animate={{ opacity: [0.1, 0.2, 0.1] }}
                transition={{ duration: 2, repeat: Infinity }}
                className="absolute inset-0 bg-blue-500/5 mix-blend-overlay"
            />
        </div>
    );
};
