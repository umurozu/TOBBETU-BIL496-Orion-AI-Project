/**
 * EditingView — LLD §3.2.1, Class: EditingOptionsView
 *
 * AI editing options panel displayed alongside the canvas.
 * Each editing type triggers the backend /process endpoint
 * via EditingController (Facade pattern).
 *
 * Tabs reflect backend AI models:
 *   - Object Removal    → SegmentationModel + InpaintingModel
 *   - Background Replace → InpaintingModel
 *   - Enhancement        → EnhancementModel
 *   - Style Transfer     → StyleTransferModel
 *   - Beautification     → BeautificationModel
 *   - Colorization       → ColorizationModel
 *   - Hair Refiner       → HairRefinerModel (brush-enabled)
 *
 * Tabs with `toolConfig` render interactive brush/slider controls
 * via the reusable EditingToolPanel component.
 */

import { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Scissors,
    ImageMinus,
    Zap,
    Palette,
    Star,
    Sun,
    Loader2,
    ChevronRight,
    Smile,
} from 'lucide-react';
import { useEditorStore } from '../store/editorStore';
import { processImage, APIError } from '../services/api';
import EditingToolPanel, {
    type ToolConfig,
} from '../components/EditingToolPanel';

/* ------------------------------------------------------------------ */
/*  Tab Definitions — map 1:1 to backend AI models                     */
/* ------------------------------------------------------------------ */

interface EditingTab {
    id: string;
    label: string;
    icon: React.ReactNode;
    editingType: string;
    description: string;
    longDescription: string;
    parameters?: Record<string, unknown>;
    /** If present, renders EditingToolPanel inside expanded content */
    toolConfig?: {
        tools: ToolConfig[];
        brushEnabled?: boolean;
    };
}

const EDITING_TABS: EditingTab[] = [
    {
        id: 'face_edit',
        label: 'Face Edit',
        icon: <Smile className="w-5 h-5" />,
        editingType: 'face_edit',
        description: 'Adjust facial features',
        longDescription:
            'Independently scale eyes, nose, mouth and face contour. Uses MediaPipe for precise landmarking and localized deformation.',
        toolConfig: {
            brushEnabled: false,
            tools: [
                {
                    id: 'left_eye_scale',
                    label: 'Left Eye Size',
                    type: 'slider',
                    min: 0.7,
                    max: 1.3,
                    step: 0.01,
                    default: 1.0,
                },
                {
                    id: 'right_eye_scale',
                    label: 'Right Eye Size',
                    type: 'slider',
                    min: 0.7,
                    max: 1.3,
                    step: 0.01,
                    default: 1.0,
                },
                {
                    id: 'left_eyebrow_scale',
                    label: 'Left Eyebrow',
                    type: 'slider',
                    min: 0.7,
                    max: 1.3,
                    step: 0.01,
                    default: 1.0,
                },
                {
                    id: 'right_eyebrow_scale',
                    label: 'Right Eyebrow',
                    type: 'slider',
                    min: 0.7,
                    max: 1.3,
                    step: 0.01,
                    default: 1.0,
                },
                {
                    id: 'nose_scale',
                    label: 'Nose Size',
                    type: 'slider',
                    min: 0.8,
                    max: 1.2,
                    step: 0.01,
                    default: 1.0,
                },
                {
                    id: 'mouth_scale',
                    label: 'Mouth Size',
                    type: 'slider',
                    min: 0.8,
                    max: 1.2,
                    step: 0.01,
                    default: 1.0,
                },
                {
                    id: 'jaw_scale',
                    label: 'Jaw / Contour',
                    type: 'slider',
                    min: 0.9,
                    max: 1.1,
                    step: 0.01,
                    default: 1.0,
                },
            ],
        },
    },
    {
        id: 'object_removal',
        label: 'Object Removal',
        icon: <Scissors className="w-5 h-5" />,
        editingType: 'object_removal',
        description: 'Remove unwanted objects',
        longDescription:
            'Uses SegmentationModel to detect objects and InpaintingModel to fill the removed region with context-aware content.',
    },
    {
        id: 'background_replace',
        label: 'Background Replace',
        icon: <ImageMinus className="w-5 h-5" />,
        editingType: 'background_replace',
        description: 'Replace image background',
        longDescription:
            'Uses InpaintingModel to replace the background after foreground isolation via segmentation.',
    },
    {
        id: 'enhancement',
        label: 'Enhancement',
        icon: <Zap className="w-5 h-5" />,
        editingType: 'enhancement',
        description: 'AI-powered quality improvement',
        longDescription:
            'Uses EnhancementModel to apply sharpening, noise reduction and contrast optimization.',
    },
    {
        id: 'style_transfer',
        label: 'Style Transfer',
        icon: <Palette className="w-5 h-5" />,
        editingType: 'style_transfer',
        description: 'Apply artistic styles',
        longDescription:
            'Uses StyleTransferModel to apply neural artistic style transformations.',
        parameters: { style_id: 'impressionist' },
    },
    {
        id: 'beautification',
        label: 'Beautification',
        icon: <Star className="w-5 h-5" />,
        editingType: 'beautification',
        description: 'Portrait enhancement',
        longDescription:
            'Uses BeautificationModel for skin smoothing and facial feature enhancement.',
    },
    {
        id: 'colorization',
        label: 'Colorization',
        icon: <Sun className="w-5 h-5" />,
        editingType: 'colorization',
        description: 'Add color to grayscale',
        longDescription:
            'Uses ColorizationModel to automatically colorize grayscale images using deep learning.',
    },
];

/* ------------------------------------------------------------------ */
/*  Face Reshape Dedicated Panel                                       */
/* ------------------------------------------------------------------ */

export const FaceReshapePanel: React.FC = () => {
    const { sessionId, setProcessedImage, setResultId, setProcessingStatus, setCurrentView, setError, processingStatus } = useEditorStore();
    const [isProcessing, setIsProcessing] = useState(false);
    const paramsRef = useRef<Record<string, unknown>>({});

    const faceTab = EDITING_TABS.find(t => t.id === 'face_edit')!;

    const handleProcess = async () => {
        if (!sessionId) return;
        setIsProcessing(true);
        setProcessingStatus('processing');

        try {
            const response = await processImage(sessionId, 'face_edit', paramsRef.current);
            if (response.status === 'success' && response.data) {
                const dataUrl = `data:image/${response.data.format};base64,${response.data.result_image}`;
                setProcessedImage(dataUrl);
                setResultId(response.data.result_id);
                setProcessingStatus('completed');
                setCurrentView('preview');
            }
        } catch (e: any) {
            setError(e.message || 'Processing failed');
            setProcessingStatus('error');
        } finally {
            setIsProcessing(false);
        }
    };

    return (
        <div className="p-4 flex flex-col gap-4">
            <p className="text-white/50 text-xs leading-relaxed">
                {faceTab.longDescription}
            </p>
            
            <EditingToolPanel
                tools={faceTab.toolConfig!.tools}
                brushEnabled={false}
                onParametersChange={(params) => {
                    paramsRef.current = params;
                }}
            />

            <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={handleProcess}
                disabled={isProcessing || processingStatus === 'processing'}
                className="w-full flex items-center justify-center gap-2 p-3 rounded-xl bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 transition-all disabled:opacity-50"
            >
                {isProcessing ? (
                    <>
                        <Loader2 className="w-4 h-4 text-white animate-spin" />
                        <span className="text-white text-sm font-semibold">Processing...</span>
                    </>
                ) : (
                    <span className="text-white text-sm font-semibold">Apply Face Reshape</span>
                )}
            </motion.button>
        </div>
    );
};

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function EditingView() {
    const {
        sessionId,
        setProcessedImage,
        setResultId,
        setProcessingStatus,
        setCurrentView,
        setError,
        processingStatus,
    } = useEditorStore();

    const [activeTabId, setActiveTabId] = useState<string | null>(null);
    const [processingTabId, setProcessingTabId] = useState<string | null>(null);

    // Track per-tab tool parameters (collected from EditingToolPanel)
    const tabParamsRef = useRef<Record<string, Record<string, unknown>>>({});

    /** Called by EditingToolPanel when user adjusts sliders/brush */
    const handleToolParametersChange = (
        tabId: string,
        params: Record<string, unknown>
    ) => {
        tabParamsRef.current[tabId] = params;
    };

    /** Sends processing request to backend EditingController via POST /process */
    const handleProcess = async (tab: EditingTab) => {
        if (!sessionId) return;

        setActiveTabId(tab.id);
        setProcessingTabId(tab.id);
        setProcessingStatus('processing');

        // Merge static parameters with dynamic tool parameters
        const toolParams = tabParamsRef.current[tab.id] || {};
        const mergedParams = { ...(tab.parameters || {}), ...toolParams };

        try {
            const response = await processImage(
                sessionId,
                tab.editingType,
                mergedParams
            );

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
                setError('Processing failed. Please try again.');
            }
            setProcessingStatus('error');
        } finally {
            setProcessingTabId(null);
        }
    };

    const isProcessing = processingStatus === 'processing';

    return (
        <div className="flex flex-col gap-1 p-4 w-full">
            <h3 className="text-white/70 text-xs font-semibold uppercase tracking-wider mb-3">
                AI Editing
            </h3>

            {/* Tab List */}
            {EDITING_TABS.map((tab) => {
                const isActive = activeTabId === tab.id;
                const isCurrentlyProcessing = processingTabId === tab.id;
                const hasTools = !!tab.toolConfig;

                return (
                    <div key={tab.id} className="mb-1">
                        {/* Tab Button */}
                        <motion.button
                            whileHover={{ scale: 1.01 }}
                            whileTap={{ scale: 0.99 }}
                            onClick={() => setActiveTabId(isActive ? null : tab.id)}
                            disabled={isProcessing}
                            className={`
                                w-full flex items-center gap-3 p-3 rounded-xl
                                transition-all duration-200
                                ${isActive
                                    ? 'bg-blue-500/20 border border-blue-500/50'
                                    : 'bg-white/5 hover:bg-white/10 border border-transparent'
                                }
                                disabled:opacity-50 disabled:cursor-not-allowed
                            `}
                        >
                            <div
                                className={`
                                    flex items-center justify-center w-10 h-10 rounded-lg
                                    ${isActive ? 'bg-blue-500/30' : 'bg-white/10'}
                                `}
                            >
                                {isCurrentlyProcessing ? (
                                    <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />
                                ) : (
                                    <span className="text-white/70">{tab.icon}</span>
                                )}
                            </div>
                            <div className="text-left flex-1">
                                <div className="flex items-center gap-2">
                                    <p className="text-white text-sm font-medium">{tab.label}</p>
                                    {hasTools && (
                                        <span className="px-1.5 py-0.5 text-[9px] font-bold bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-full uppercase tracking-wider">
                                            Brush
                                        </span>
                                    )}
                                </div>
                                <p className="text-white/40 text-xs">{tab.description}</p>
                            </div>
                            <ChevronRight
                                className={`w-4 h-4 text-white/30 transition-transform duration-200 ${isActive ? 'rotate-90' : ''
                                    }`}
                            />
                        </motion.button>

                        {/* Expanded Tab Content */}
                        <AnimatePresence>
                            {isActive && (
                                <motion.div
                                    initial={{ height: 0, opacity: 0 }}
                                    animate={{ height: 'auto', opacity: 1 }}
                                    exit={{ height: 0, opacity: 0 }}
                                    transition={{ duration: 0.2 }}
                                    className="overflow-hidden"
                                >
                                    <div className="px-3 py-3 ml-4 mt-1 border-l-2 border-blue-500/30">
                                        <p className="text-white/50 text-xs leading-relaxed mb-3">
                                            {tab.longDescription}
                                        </p>

                                        {/* Tool Panel — brush/sliders/toggles */}
                                        {tab.toolConfig && (
                                            <div className="mb-3">
                                                <EditingToolPanel
                                                    tools={tab.toolConfig.tools}
                                                    brushEnabled={tab.toolConfig.brushEnabled}
                                                    onParametersChange={(params) =>
                                                        handleToolParametersChange(tab.id, params)
                                                    }
                                                />
                                            </div>
                                        )}

                                        {/* Process Button */}
                                        <motion.button
                                            whileHover={{ scale: 1.02 }}
                                            whileTap={{ scale: 0.98 }}
                                            onClick={() => handleProcess(tab)}
                                            disabled={isProcessing}
                                            className="w-full flex items-center justify-center gap-2 p-2.5 rounded-lg bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                                        >
                                            {isCurrentlyProcessing ? (
                                                <>
                                                    <Loader2 className="w-4 h-4 text-white animate-spin" />
                                                    <span className="text-white text-xs font-semibold">
                                                        Processing...
                                                    </span>
                                                </>
                                            ) : (
                                                <span className="text-white text-xs font-semibold">
                                                    Apply {tab.label}
                                                </span>
                                            )}
                                        </motion.button>
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>
                );
            })}
        </div>
    );
}
