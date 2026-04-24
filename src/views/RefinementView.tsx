/**
 * RefinementView — LLD §3.2.1, Class: RefinementView
 *
 * Provides brush-based interaction for manual mask refinement
 * after AI segmentation. Communicates with RefinementController.
 */

import { useState } from 'react';
import { motion } from 'framer-motion';
import {
    Paintbrush,
    Minus,
    Plus,
    RotateCcw,
    Check,
    ArrowLeft,
    Loader2,
} from 'lucide-react';
import { useEditorStore } from '../store/editorStore';
import { refineMask, regenerateImage, APIError } from '../services/api';

export default function RefinementView() {
    const {
        sessionId,
        setProcessedImage,
        setResultId,
        setProcessingStatus,
        setCurrentView,
        setError,
    } = useEditorStore();

    const [brushSize, setBrushSize] = useState(10);
    const [brushStrength, setBrushStrength] = useState(1.0);
    const [isRefining, setIsRefining] = useState(false);
    const [isRegenerating, setIsRegenerating] = useState(false);
    const [refinedMaskData, setRefinedMaskData] = useState<string | null>(null);

    /** Sends mask refinement data to the backend RefinementController */
    const handleRefineMask = async () => {
        if (!sessionId) return;

        setIsRefining(true);
        try {
            const response = await refineMask(
                sessionId,
                refinedMaskData || '',
                brushSize,
                brushStrength
            );

            if (response.status === 'success' && response.data) {
                const data = response.data as Record<string, unknown>;
                if (data.mask_data) {
                    setRefinedMaskData(data.mask_data as string);
                }
            }
        } catch (e: unknown) {
            if (e instanceof APIError) {
                setError(e.message, e.errorCode);
            } else {
                setError('Refinement failed. Please try again.');
            }
        } finally {
            setIsRefining(false);
        }
    };

    /** Regenerates the image using the refined mask via RefinementController */
    const handleRegenerate = async () => {
        if (!sessionId || !refinedMaskData) return;

        setIsRegenerating(true);
        setProcessingStatus('processing');

        try {
            const response = await regenerateImage(sessionId, refinedMaskData);

            if (response.status === 'success' && response.data) {
                const dataUrl = `data:image/${response.data.format};base64,${response.data.result_image}`;
                setProcessedImage(dataUrl);
                setResultId(response.data.result_id);
                setProcessingStatus('completed');
                setCurrentView('preview');
            }
        } catch (e: unknown) {
            if (e instanceof APIError) {
                setError(e.message, e.errorCode);
            } else {
                setError('Regeneration failed. Please try again.');
            }
            setProcessingStatus('error');
        } finally {
            setIsRegenerating(false);
        }
    };

    return (
        <div className="flex flex-col gap-4 p-4 w-full">
            <h3 className="text-white/70 text-xs font-semibold uppercase tracking-wider mb-1">
                Mask Refinement
            </h3>

            {/* Brush Size Control */}
            <div className="bg-white/5 rounded-xl p-3">
                <div className="flex items-center gap-2 mb-2">
                    <Paintbrush className="w-4 h-4 text-white/50" />
                    <span className="text-white/70 text-xs font-medium">Brush Size</span>
                    <span className="ml-auto text-white/50 text-xs">{brushSize}px</span>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => setBrushSize(Math.max(1, brushSize - 2))}
                        className="p-1 rounded bg-white/10 hover:bg-white/20 transition-colors"
                    >
                        <Minus className="w-3 h-3 text-white/70" />
                    </button>
                    <input
                        type="range"
                        min="1"
                        max="50"
                        value={brushSize}
                        onChange={(e) => setBrushSize(Number(e.target.value))}
                        className="flex-1 h-1 bg-white/20 rounded-lg appearance-none cursor-pointer accent-blue-500"
                    />
                    <button
                        onClick={() => setBrushSize(Math.min(50, brushSize + 2))}
                        className="p-1 rounded bg-white/10 hover:bg-white/20 transition-colors"
                    >
                        <Plus className="w-3 h-3 text-white/70" />
                    </button>
                </div>
            </div>

            {/* Brush Strength Control */}
            <div className="bg-white/5 rounded-xl p-3">
                <div className="flex items-center gap-2 mb-2">
                    <Paintbrush className="w-4 h-4 text-white/50" />
                    <span className="text-white/70 text-xs font-medium">Brush Strength</span>
                    <span className="ml-auto text-white/50 text-xs">
                        {Math.round(brushStrength * 100)}%
                    </span>
                </div>
                <input
                    type="range"
                    min="0.1"
                    max="1.0"
                    step="0.1"
                    value={brushStrength}
                    onChange={(e) => setBrushStrength(Number(e.target.value))}
                    className="w-full h-1 bg-white/20 rounded-lg appearance-none cursor-pointer accent-blue-500"
                />
            </div>

            {/* Action Buttons */}
            <div className="flex flex-col gap-2 mt-2">
                {/* Apply Refinement */}
                <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={handleRefineMask}
                    disabled={isRefining || isRegenerating}
                    className="flex items-center justify-center gap-2 p-3 rounded-xl bg-purple-500/20 hover:bg-purple-500/30 border border-purple-500/50 transition-all disabled:opacity-50"
                >
                    {isRefining ? (
                        <Loader2 className="w-5 h-5 text-purple-400 animate-spin" />
                    ) : (
                        <Paintbrush className="w-5 h-5 text-purple-400" />
                    )}
                    <span className="text-white text-sm font-medium">
                        {isRefining ? 'Refining...' : 'Apply Refinement'}
                    </span>
                </motion.button>

                {/* Regenerate with Refined Mask */}
                <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={handleRegenerate}
                    disabled={!refinedMaskData || isRegenerating || isRefining}
                    className="flex items-center justify-center gap-2 p-3 rounded-xl bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 transition-all disabled:opacity-50"
                >
                    {isRegenerating ? (
                        <Loader2 className="w-5 h-5 text-white animate-spin" />
                    ) : (
                        <Check className="w-5 h-5 text-white" />
                    )}
                    <span className="text-white text-sm font-semibold">
                        {isRegenerating ? 'Regenerating...' : 'Regenerate Image'}
                    </span>
                </motion.button>

                {/* Reset Refinement */}
                <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => setRefinedMaskData(null)}
                    disabled={!refinedMaskData}
                    className="flex items-center gap-2 p-3 rounded-xl bg-white/5 hover:bg-white/10 transition-all disabled:opacity-30"
                >
                    <RotateCcw className="w-4 h-4 text-white/50" />
                    <span className="text-white/50 text-sm">Reset Mask</span>
                </motion.button>

                {/* Back to Preview */}
                <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => setCurrentView('preview')}
                    className="flex items-center gap-2 p-3 rounded-xl bg-white/5 hover:bg-white/10 transition-all"
                >
                    <ArrowLeft className="w-4 h-4 text-white/50" />
                    <span className="text-white/50 text-sm">Back to Preview</span>
                </motion.button>
            </div>
        </div>
    );
}
