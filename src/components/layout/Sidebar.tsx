import React from 'react';
import {
    Home, Wand2, User, Image as ImageIcon,
    Sparkles, Scissors, ImageMinus,
    Zap, Palette, Star, Sun, Loader2, RotateCcw, Trash2, LayoutGrid, Clock3, Shield, ArrowLeftRight
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { APIError, deleteSession, generateHairTransfer, processImage, uploadImage } from '../../services/api';
import { useEditorStore } from '../../store/editorStore';
import { cn } from '../../lib/utils';
import { Smile } from 'lucide-react';
import { HairstyleOptions } from './HairstyleOptions';
import { DEFAULT_HAIR_COLOR } from '../../config/hairstylePresets';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type NavItem = {
    id: string;
    label: string;
    icon: React.ElementType;
    disabled?: boolean;
    children?: NavGroup[];
};

type NavGroup = {
    title: string;
    items: ToolItem[];
};

type ToolItem = {
    id: string;
    label: string;
    icon?: React.ElementType;
    badge?: 'NEW' | 'HOT';
    image?: string;
    /** Backend editing type — if set, this tool triggers AI processing */
    editingType?: string;
    /** Brush-enabled tool — shows brush controls and enables canvas overlay */
    brushEnabled?: boolean;
    /** Parameter sliders/toggles for this tool */
    toolControls?: ToolControl[];
};

type ToolControl =
    | { id: string; label: string; type: 'slider'; min: number; max: number; step: number; default: number; unit?: string }
    | { id: string; label: string; type: 'toggle'; default: boolean };

const formatToolValue = (control: ToolControl, rawValue: unknown) => {
    if (control.type !== 'slider') {
        return String(rawValue);
    }

    const numericValue = Number(rawValue);
    if (control.unit === '%') {
        return `${Math.round(numericValue * 100)}%`;
    }
    if (control.unit === 'x') {
        return `${numericValue}x`;
    }
    if (Number.isInteger(numericValue)) {
        return String(numericValue);
    }
    return numericValue.toFixed(2).replace(/0+$/, '').replace(/\.$/, '');
};

/* ------------------------------------------------------------------ */
/*  Navigation Config                                                  */
/* ------------------------------------------------------------------ */

const NAV_ITEMS: NavItem[] = [
    { id: 'home', label: 'Home', icon: Home },
    { 
        id: 'face-reshape', 
        label: 'Face Reshape', 
        icon: Smile,
        children: [
            {
                title: 'Facial Feature Scaling',
                items: [
                    {
                        id: 'face_reshape_tool',
                        label: 'Face Reshape',
                        icon: Smile,
                        editingType: 'face_edit',
                        toolControls: [
                            { id: 'mesh_mode', label: 'Interactive Mesh', type: 'toggle', default: true },
                            { id: 'mesh_points_visibility', label: 'Show Control Points', type: 'toggle', default: true },
                        ]
                    }
                ]
            }
        ]
    },
    {
        id: 'ai-editing',
        label: 'AI Editing Tools',
        icon: Wand2,
        children: [
            {
                title: 'Image Processing',
                items: [
                    {
                        id: 'object_removal',
                        label: 'Object Removal',
                        icon: Scissors,
                        editingType: 'object_removal',
                        brushEnabled: true,
                        toolControls: [
                            { id: 'brush_action', label: 'Erase Mode (Remove from Mask)', type: 'toggle', default: false },
                        ],
                    },
                    {
                        id: 'background_removal',
                        label: 'BG Removal',
                        icon: ImageMinus,
                        editingType: 'background_replace', // U2Net triggers standard Canvas BG Removal when passed via API
                        brushEnabled: true,
                        toolControls: [
                            { id: 'brush_action', label: 'Erase Mode (Remove from Mask)', type: 'toggle', default: false },
                        ],
                    },
                    {
                        id: 'background_replace',
                        label: 'BG Replace (Dual)',
                        icon: ImageIcon,
                    },
                    {
                        id: 'enhancement',
                        label: 'Resolution Boost',
                        icon: Zap,
                        editingType: 'enhancement',
                        toolControls: [
                            { id: 'upscale', label: 'Upscale', type: 'slider', min: 1, max: 4, step: 1, default: 2, unit: 'x' },
                            { id: 'detail_boost', label: 'Detail Recovery', type: 'slider', min: 0, max: 1, step: 0.05, default: 0.45, unit: '%' },
                            { id: 'denoise', label: 'Noise Cleanup', type: 'slider', min: 0, max: 1, step: 0.05, default: 0.2, unit: '%' },
                        ],
                    },

                    {
                        id: 'beautification',
                        label: 'Face Enhance',
                        icon: Star,
                        editingType: 'beautification',
                        toolControls: [
                            { id: 'skin_smoothing', label: 'Skin Smoothing', type: 'slider', min: 0, max: 1, step: 0.05, default: 0.55, unit: '%' },
                            { id: 'detail_boost', label: 'Feature Definition', type: 'slider', min: 0, max: 1, step: 0.05, default: 0.45, unit: '%' },
                            { id: 'tone_balance', label: 'Radiance', type: 'slider', min: 0, max: 1, step: 0.05, default: 0.4, unit: '%' },
                        ],
                    },
                    {
                        id: 'aging_transform',
                        label: 'Age Transform',
                        icon: Clock3,
                        editingType: 'aging',
                        toolControls: [
                            { id: 'rejuvenate', label: 'Younger Mode', type: 'toggle', default: false },
                            { id: 'intensity', label: 'Transformation Strength', type: 'slider', min: 0.1, max: 1, step: 0.05, default: 0.8, unit: '%' },
                        ],
                    },
                    {
                        id: 'hairstyle',
                        label: 'Hair Color',
                        icon: Sparkles,
                        editingType: 'hairstyle',
                        brushEnabled: true,
                        toolControls: [
                            { id: 'brush_action', label: 'Erase Mode (Remove from Hair Mask)', type: 'toggle', default: false },
                        ],
                    },
                    {
                        id: 'hair_transfer',
                        label: 'Hair Transfer (3 Images)',
                        icon: ArrowLeftRight,
                    },
                    {
                        id: 'colorization',
                        label: 'Colorization',
                        icon: Sun,
                        editingType: 'colorization',
                    },
                ],
            },
        ],
    },

    { id: 'style-transfer', label: 'Style Transfer', icon: Palette },
    { id: 'community', label: 'Community', icon: Sparkles },
    { id: 'gallery', label: 'My Posts', icon: LayoutGrid },
    { id: 'detect-invisio-image', label: 'Detect Invisio', icon: Shield },
];

/* ------------------------------------------------------------------ */
/*  Inline Tool Panel (brush + sliders inside sidebar)                 */
/* ------------------------------------------------------------------ */


/* ------------------------------------------------------------------ */
/*  Sidebar Component                                                  */
/* ------------------------------------------------------------------ */

export const Sidebar: React.FC = () => {
    const standaloneSections = ['style-transfer', 'detect-invisio-image'];
    const {
        activeSection, setActiveSection,
        activeTool, setActiveTool,
        setCurrentView,
        resetForNewUpload,
        sessionId, setProcessedImage, setResultId, setProcessingStatus, setError, processingStatus,
        uploadedImage, setUploadedImage, setSessionId, setImageId
    } = useEditorStore();

    const [hairTransferShapeFile, setHairTransferShapeFile] = useState<File | null>(null);
    const [hairTransferColorFile, setHairTransferColorFile] = useState<File | null>(null);
    const [hairTransferShapePreview, setHairTransferShapePreview] = useState<string | null>(null);
    const [hairTransferColorPreview, setHairTransferColorPreview] = useState<string | null>(null);
    const [hairTransferSourceError, setHairTransferSourceError] = useState<string | null>(null);
    const hairTransferSourceInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        if (!hairTransferShapeFile) {
            setHairTransferShapePreview(null);
            return;
        }
        const url = URL.createObjectURL(hairTransferShapeFile);
        setHairTransferShapePreview(url);
        return () => URL.revokeObjectURL(url);
    }, [hairTransferShapeFile]);

    useEffect(() => {
        if (!hairTransferColorFile) {
            setHairTransferColorPreview(null);
            return;
        }
        const url = URL.createObjectURL(hairTransferColorFile);
        setHairTransferColorPreview(url);
        return () => URL.revokeObjectURL(url);
    }, [hairTransferColorFile]);

    const resetHairTransferInputs = () => {
        setHairTransferShapeFile(null);
        setHairTransferColorFile(null);
        setHairTransferSourceError(null);
    };

    const buildToolDefaults = (tool: ToolItem | undefined | null): Record<string, unknown> => {
        if (!tool) return {};
        if (tool.id === 'hairstyle') {
            return {
                hair_color: DEFAULT_HAIR_COLOR,
                brush_action: false,
            };
        }

        const defaults: Record<string, unknown> = {};
        tool.toolControls?.forEach((control) => {
            defaults[control.id] = control.default;
        });

        return defaults;
    };

    const handleResetTool = () => {
        if (!activeTool) return;

        if (activeTool === 'hair_transfer') {
            resetHairTransferInputs();
            return;
        }
        
        // 1. Reset tool parameters to defaults
        let defaults: Record<string, any> = {};
        NAV_ITEMS.forEach(nav => {
            if (nav.children) {
                nav.children.forEach(group => {
                    const tool = group.items.find((i: any) => i.id === activeTool);
                    if (tool) {
                        defaults = buildToolDefaults(tool);
                    }
                });
            }
        });
        useEditorStore.getState().setToolParameters(defaults);
        useEditorStore.getState().setBrushAction(Boolean(defaults.brush_action) ? 'erase' : 'paint');

        // 2. Clear brush strokes if it's a brush tool
        useEditorStore.getState().clearBrushStrokes();

        // 3. Special case for face reshape landmarks
        if (activeTool === 'face_reshape_tool') {
            useEditorStore.getState().resetLandmarks();
        }
    };

    const handleUploadHairTransferSource = async (file: File) => {
        setHairTransferSourceError(null);
        const previousSessionId = sessionId;
        resetForNewUpload();
        setProcessingStatus('uploading');
        try {
            const response = await uploadImage(file);
            if (response.status !== 'success' || !response.data) {
                throw new APIError(response.message || 'Upload failed', response.error_code || 'UPLOAD_ERROR', 400);
            }

            setSessionId(response.data.session_id);
            setImageId(response.data.image_id);
            setUploadedImage(URL.createObjectURL(file));
            setProcessedImage(null);
            setResultId(null);
            setCurrentView('editing');
            setProcessingStatus('idle');

            if (previousSessionId && previousSessionId !== response.data.session_id) {
                void deleteSession(previousSessionId).catch(() => {});
            }
        } catch (e: unknown) {
            if (e instanceof APIError) {
                setHairTransferSourceError(e.message);
                setProcessingStatus('idle');
                return;
            }
            if (e instanceof Error) {
                setHairTransferSourceError(e.message);
                setProcessingStatus('idle');
                return;
            }
            setHairTransferSourceError('Upload failed. Please try again.');
            setProcessingStatus('idle');
        }
    };

    const handleApplyHairTransfer = async () => {
        if (!sessionId) {
            setHairTransferSourceError('Source image not uploaded yet.');
            return;
        }
        if (!hairTransferShapeFile || !hairTransferColorFile) {
            setHairTransferSourceError('Select both Shape and Color reference images.');
            return;
        }

        setProcessingStatus('processing');
        try {
            const response = await generateHairTransfer(sessionId, hairTransferShapeFile, hairTransferColorFile);
            if (response.status === 'success' && response.data) {
                const dataUrl = `data:image/${response.data.format};base64,${response.data.result_image}`;
                setProcessedImage(dataUrl);
                setResultId(response.data.result_id);
                setProcessingStatus('completed');
            } else {
                throw new APIError(response.message || 'Hair transfer failed', response.error_code || 'HAIR_TRANSFER_ERROR', 400);
            }
        } catch (e: unknown) {
            if (e instanceof APIError) {
                setError(e.message || 'Hair transfer failed', e.errorCode);
                setProcessingStatus('error');
                return;
            }
            if (e instanceof Error) {
                setError(e.message || 'Hair transfer failed');
                setProcessingStatus('error');
                return;
            }
            setError('Hair transfer failed');
            setProcessingStatus('error');
        }
    };

    const handleApplyAIEditing = async () => {
        if (!sessionId || !activeTool) return;
        
        let editingType = '';
        let brushEnabled = false;
        NAV_ITEMS.forEach(nav => {
            if (nav.children) {
                nav.children.forEach(group => {
                    const found = group.items.find((i: any) => i.id === activeTool);
                    if (found && (found as any).editingType) {
                        editingType = (found as any).editingType;
                        brushEnabled = !!(found as any).brushEnabled;
                    }
                });
            }
        });

        if (!editingType) return;

        setProcessingStatus('processing');
        try {
            const { toolParameters, maskData, objectRemovalMaskData, brushSize, brushStrength, brushAction } = useEditorStore.getState();
            const effectiveMaskData = editingType === 'object_removal' ? objectRemovalMaskData : maskData;

            // Object removal / inpainting requires a user-provided mask.
            if ((editingType === 'object_removal' || editingType === 'inpainting') && !effectiveMaskData) {
                setError('Draw a mask on the image first (paint the area you want to remove).', 'MASK_REQUIRED');
                setProcessingStatus('idle');
                return;
            }
            const response = await processImage(sessionId, editingType, {
                ...toolParameters,
                ...(brushEnabled
                    ? {
                        brush_size: brushSize,
                        brush_strength: brushStrength,
                        brush_action: brushAction === 'erase',
                    }
                    : {}),
                ...(effectiveMaskData ? { mask_data: effectiveMaskData } : {}),
            });
            if (response.status === 'success' && response.data) {
                const dataUrl = `data:image/${response.data.format};base64,${response.data.result_image}`;
                setProcessedImage(dataUrl);
                setResultId(response.data.result_id);
                setProcessingStatus('completed');
            }
        } catch (e: any) {
            setError(e.message || 'Processing failed');
            setProcessingStatus('error');
        }
    };

    return (
        <div className="flex h-full z-20 shadow-lg shadow-slate-200/40 bg-white relative">
            {/* Column 1: Slim Icon Sidebar */}
            <div className="w-[88px] h-full border-r border-slate-200 flex flex-col py-2 shrink-0 bg-white overflow-y-auto custom-scrollbar">
                {NAV_ITEMS.map((item) => (
                    <button
                        key={item.id}
                        onClick={() => {
                            if (!item.disabled) {
                                setActiveSection(item.id);
                                if (item.id === 'community') {
                                    setCurrentView('community');
                                } else if (item.id === 'gallery') {
                                    setCurrentView('my_posts');
                                } else if (['home', 'face-reshape', 'ai-editing', 'batch', 'portrait', 'basic-edit'].includes(item.id)) {
                                    const state = useEditorStore.getState();
                                    if (state.currentView === 'community' || state.currentView === 'my_posts') {
                                         setCurrentView(state.uploadedImage ? 'editing' : 'upload');
                                    }

                                    // Auto-activate the tool for Face Reshape to show sliders immediately
                                    if (item.id === 'face-reshape') {
                                        setActiveTool('face_reshape_tool');
                                        const tool = item.children?.[0]?.items?.[0];
                                        if (tool) {
                                            useEditorStore.getState().setToolParameters(buildToolDefaults(tool));
                                        }
                                    }
                                }

                                if (standaloneSections.includes(item.id)) {
                                    setActiveTool(item.id);
                                } else if (activeTool && standaloneSections.includes(activeTool)) {
                                    setActiveTool(null);
                                }
                            }
                        }}
                        disabled={item.disabled}
                        className={cn(
                            "flex flex-col items-center justify-center py-[14px] px-2 w-full transition-colors relative group",
                            activeSection === item.id
                                ? "text-[#00a6ed]"
                                : "text-slate-500 hover:text-slate-800",
                            item.disabled && "opacity-50 cursor-not-allowed"
                        )}
                    >
                        {activeSection === item.id && (
                            <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-[#00a6ed] rounded-r" />
                        )}
                        <div className={cn("p-2 rounded-2xl mb-1 transition-colors", activeSection === item.id ? "bg-blue-50/50" : "group-hover:bg-slate-50")}>
                            <item.icon size={22} strokeWidth={activeSection === item.id ? 2.5 : 2} />
                        </div>
                        <span className="text-[12px] font-semibold text-center leading-tight">
                            {item.label}
                        </span>
                    </button>
                ))}
            </div>

            {/* Column 2: Details panel (children tools) */}
            <div className="w-[300px] h-full border-r border-slate-200 flex flex-col shrink-0 bg-white">
                {(() => {
                    const activeItem = NAV_ITEMS.find(n => n.id === activeSection);

                    if (!activeItem) return null;

                    if (!activeItem.children) {
                        return (
                            <div className="p-8 text-center text-slate-400">
                                <activeItem.icon size={48} className="mx-auto mb-4 opacity-20" />
                                <p className="text-sm font-medium">Select a feature from the menu to see options.</p>
                            </div>
                        );
                    }

                    return (
                        <div className="flex flex-col h-full bg-white relative">
                            {/* Panel Header */}
                            <div className="px-5 py-5 border-b border-slate-100 shrink-0">
                                <h2 className="text-[17px] font-bold text-[#00a6ed] mb-1.5 tracking-tight">
                                    {(activeItem.id === 'portrait' && activeTool === 'hairstyle')
                                        ? 'Hair Recolor'
                                        : (activeItem.id === 'portrait' && activeTool === 'hair_transfer')
                                            ? 'Hair Transfer (3 Images)'
                                        : activeItem.id === 'portrait' ? 'AI Portrait Tools' : activeItem.label}
                                </h2>
                                <p className="text-[13px] text-slate-500 font-medium">
                                    {(activeItem.id === 'portrait' && activeTool === 'hairstyle')
                                        ? 'Mask and recolor the hair that already exists in your photo'
                                        : (activeItem.id === 'portrait' && activeTool === 'hair_transfer')
                                            ? 'Pick shape + color references and transfer them onto your source image'
                                        : 'Select a style to apply'}
                                </p>

                                {/* Quick Tabs (Hardcoded for styling, matches screenshot) */}
                                {activeItem.id === 'portrait' && (
                                    <div className="mt-4 shrink-0">
                                        <div className="flex items-center gap-5 border-b border-slate-200">
                                            {['NEW', 'HOT', 'Styles', 'Bangs', 'Wavy'].map((tab, idx) => (
                                                <button key={tab} className={cn("text-[13px] pb-2 font-bold transition-colors", idx === 2 ? "text-[#00a6ed] border-b-[3px] border-[#00a6ed]" : "text-slate-500 border-b-[3px] border-transparent hover:text-slate-800")}>
                                                    {tab}
                                                </button>
                                            ))}
                                        </div>
                                        <div className="flex items-center bg-slate-100 p-[3px] mt-4 rounded-full w-48 mx-auto border border-slate-200">
                                            <button className="flex-1 bg-[#00a6ed] text-white text-[13px] font-bold py-1.5 rounded-full shadow-sm">Female</button>
                                            <button className="flex-1 text-slate-600 text-[13px] font-bold py-1.5 rounded-full hover:bg-slate-200 transition-colors">Male</button>
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* Tool Grid Content */}
                            <div className="flex-1 overflow-y-auto custom-scrollbar p-5 space-y-6">
                                {activeItem.children.map((group, gIdx) => (
                                    <div key={group.title + gIdx}>
                                        {/* Optional Title for non-portrait views, or keep empty if portrait */}
                                        {activeItem.id !== 'portrait' && (
                                            <h4 className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-3 px-1">
                                                {group.title}
                                            </h4>
                                        )}

                                        <div className={cn("grid gap-3", group.items.some(t => t.editingType) ? "grid-cols-1" : "grid-cols-3")}>
                                            {group.items.map((tool) => {
                                                const isSelected = activeTool === tool.id;
                                                const isListLayout = group.items.some(t => (t as any).editingType);

                                                if (isListLayout) {
                                                    // List Layout (like AI Editing Tools)
                                                    return (
                                                        <div key={tool.id} className="space-y-2">
                                                            <button
                                                                onClick={() => {
                                                                    setActiveTool(tool.id);
                                                                    const state = useEditorStore.getState();
                                                                    if (tool.id !== activeTool) {
                                                                        state.clearBrushStrokes();
                                                                    }
                                                                    state.setBrushMode(!!tool.brushEnabled);
                                                                    const defaults = buildToolDefaults(tool);
                                                                    state.setToolParameters(defaults);
                                                                    state.setBrushAction(Boolean(defaults.brush_action) ? 'erase' : 'paint');
                                                                }}
                                                                className={cn("w-full flex items-center gap-3 p-3 rounded-xl transition-all text-left border", isSelected ? "bg-blue-50 border-[#00a6ed] shadow-sm" : "bg-white border-slate-200 hover:border-blue-300")}
                                                            >
                                                                <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-600 flex items-center justify-center">
                                                                    {tool.icon ? <tool.icon size={16} /> : <Zap size={16} />}
                                                                </div>
                                                                <span className="text-sm font-bold text-slate-700">{tool.label}</span>
                                                            </button>

                                                            {/* Tool Controls (Sliders/Toggles) */}
                                                            {isSelected && (
                                                                <div className="bg-slate-50/50 rounded-xl p-4 border border-slate-100 space-y-4 animate-in fade-in slide-in-from-top-2">
                                                                    {/* Brush Mode Controls */}
                                                                    {tool.brushEnabled && (
                                                                        <div className="space-y-4 border-b border-slate-200 pb-4 mb-4">
                                                                            <div className="space-y-2">
                                                                                <div className="flex justify-between">
                                                                                    <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Brush Size</label>
                                                                                    <span className="text-[11px] font-bold text-[#00a6ed]">{useEditorStore.getState().brushSize}px</span>
                                                                                </div>
                                                                                <input
                                                                                    type="range" min="1" max="100"
                                                                                    value={useEditorStore.getState().brushSize}
                                                                                    onChange={(e) => useEditorStore.getState().setBrushSize(parseInt(e.target.value))}
                                                                                    className="w-full h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-[#00a6ed]"
                                                                                />
                                                                            </div>
                                                                            
                                                                            <div className="flex gap-2">
                                                                                <button
                                                                                    onClick={() => useEditorStore.getState().undoBrushStroke()}
                                                                                    disabled={useEditorStore.getState().brushStrokes.length === 0}
                                                                                    className="flex-1 py-1.5 px-3 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-600 text-[11px] font-bold flex items-center justify-center gap-1.5 transition-colors disabled:opacity-40"
                                                                                >
                                                                                    <RotateCcw size={12} /> Undo
                                                                                </button>
                                                                                <button
                                                                                    onClick={() => useEditorStore.getState().clearBrushStrokes()}
                                                                                    disabled={useEditorStore.getState().brushStrokes.length === 0}
                                                                                    className="flex-1 py-1.5 px-3 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-600 text-[11px] font-bold flex items-center justify-center gap-1.5 transition-colors disabled:opacity-40"
                                                                                >
                                                                                    <Trash2 size={12} /> Clear
                                                                                </button>
                                                                            </div>
                                                                        </div>
                                                                    )}

                                                                    {tool.id === 'hairstyle' && (
                                                                        <HairstyleOptions
                                                                            selectedColorId={(useEditorStore.getState().toolParameters.hair_color as string | undefined) ?? null}
                                                                            onSelectColorId={(colorId) => {
                                                                                useEditorStore.getState().setToolParameters({
                                                                                    ...useEditorStore.getState().toolParameters,
                                                                                    hair_color: colorId,
                                                                                });
                                                                            }}
                                                                        />
                                                                    )}

                                                                    {tool.id === 'hair_transfer' && (
                                                                        <div className="space-y-4 border-t border-slate-200 pt-4">
                                                                            <div className="rounded-2xl bg-slate-50 border border-slate-200 p-3">
                                                                                <p className="text-[12px] font-bold text-slate-700">Source</p>
                                                                                <p className="text-[12px] text-slate-500 mt-1">
                                                                                    Uses your current uploaded image. You can replace it here if needed.
                                                                                </p>

                                                                                <div className="mt-3 flex items-center gap-3">
                                                                                    <div className="w-14 h-14 rounded-xl border border-slate-200 overflow-hidden bg-white shrink-0">
                                                                                        {uploadedImage ? (
                                                                                            <img src={uploadedImage} alt="Source" className="w-full h-full object-cover" />
                                                                                        ) : (
                                                                                            <div className="w-full h-full bg-slate-100 flex items-center justify-center text-slate-400 text-[12px] font-bold">
                                                                                                No Image
                                                                                            </div>
                                                                                        )}
                                                                                    </div>
                                                                                    <div className="flex-1">
                                                                                        <button
                                                                                            type="button"
                                                                                            onClick={() => hairTransferSourceInputRef.current?.click()}
                                                                                            className="w-full border-2 border-[#00a6ed] text-[#00a6ed] font-bold py-2 rounded-xl text-[12px] hover:bg-blue-50 transition-colors"
                                                                                        >
                                                                                            {sessionId ? 'Replace Source Image' : 'Upload Source Image'}
                                                                                        </button>
                                                                                        <input
                                                                                            ref={hairTransferSourceInputRef}
                                                                                            type="file"
                                                                                            accept="image/*"
                                                                                            className="hidden"
                                                                                            onChange={(e) => {
                                                                                                const file = e.target.files?.[0];
                                                                                                if (file) handleUploadHairTransferSource(file);
                                                                                            }}
                                                                                        />
                                                                                    </div>
                                                                                </div>

                                                                                {hairTransferSourceError && (
                                                                                    <p className="mt-2 text-[12px] text-red-500 font-semibold">{hairTransferSourceError}</p>
                                                                                )}
                                                                            </div>

                                                                            <div className="grid grid-cols-2 gap-3">
                                                                                <div className="rounded-2xl bg-white border border-slate-200 p-3 space-y-2">
                                                                                    <p className="text-[12px] font-bold text-slate-700">Shape</p>
                                                                                    <div className="w-full aspect-[4/3] rounded-xl border border-slate-200 overflow-hidden bg-slate-50">
                                                                                        {hairTransferShapePreview ? (
                                                                                            <img src={hairTransferShapePreview} alt="Shape reference" className="w-full h-full object-cover" />
                                                                                        ) : (
                                                                                            <div className="w-full h-full flex items-center justify-center text-slate-400 text-[12px] font-bold">
                                                                                                Select
                                                                                            </div>
                                                                                        )}
                                                                                    </div>
                                                                                    <input
                                                                                        type="file"
                                                                                        accept="image/*"
                                                                                        className="block w-full text-[11px] text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-[11px] file:font-bold file:text-slate-700 hover:file:bg-slate-200"
                                                                                        onChange={(e) => setHairTransferShapeFile(e.target.files?.[0] ?? null)}
                                                                                    />
                                                                                </div>

                                                                                <div className="rounded-2xl bg-white border border-slate-200 p-3 space-y-2">
                                                                                    <p className="text-[12px] font-bold text-slate-700">Color</p>
                                                                                    <div className="w-full aspect-[4/3] rounded-xl border border-slate-200 overflow-hidden bg-slate-50">
                                                                                        {hairTransferColorPreview ? (
                                                                                            <img src={hairTransferColorPreview} alt="Color reference" className="w-full h-full object-cover" />
                                                                                        ) : (
                                                                                            <div className="w-full h-full flex items-center justify-center text-slate-400 text-[12px] font-bold">
                                                                                                Select
                                                                                            </div>
                                                                                        )}
                                                                                    </div>
                                                                                    <input
                                                                                        type="file"
                                                                                        accept="image/*"
                                                                                        className="block w-full text-[11px] text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-[11px] file:font-bold file:text-slate-700 hover:file:bg-slate-200"
                                                                                        onChange={(e) => setHairTransferColorFile(e.target.files?.[0] ?? null)}
                                                                                    />
                                                                                </div>
                                                                            </div>
                                                                        </div>
                                                                    )}

                                                                    {/* Custom Tool Controls */}
                                                                    {tool.toolControls?.map(control => (
                                                                        <div key={control.id} className="space-y-2">
                                                                            {control.type === 'slider' ? (
                                                                                <>
                                                                                    <div className="flex justify-between">
                                                                                        <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">{control.label}</label>
                                                                                        <span className="text-[11px] font-bold text-[#00a6ed]">
                                                                                            {formatToolValue(control, useEditorStore.getState().toolParameters[control.id] ?? control.default)}
                                                                                        </span>
                                                                                    </div>
                                                                                    <input
                                                                                        type="range" min={control.min} max={control.max} step={control.step}
                                                                                        value={Number(useEditorStore.getState().toolParameters[control.id] ?? control.default)}
                                                                                        onChange={(e) => {
                                                                                            const val = parseFloat(e.target.value);
                                                                                            useEditorStore.getState().setToolParameters({ ...useEditorStore.getState().toolParameters, [control.id]: val });
                                                                                        }}
                                                                                        className="w-full h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-[#00a6ed]"
                                                                                    />
                                                                                </>
                                                                            ) : (
                                                                                <div className="flex items-center justify-between">
                                                                                    <label className="text-[12px] font-bold text-slate-600">{control.label}</label>
                                                                                    <button
                                                                                        onClick={() => {
                                                                                            const current = !!(useEditorStore.getState().toolParameters[control.id] ?? control.default);
                                                                                            const next = !current;
                                                                                            useEditorStore.getState().setToolParameters({ ...useEditorStore.getState().toolParameters, [control.id]: next });
                                                                                            // Sync to explicit brushAction if it's the brush_action toggle
                                                                                            if (control.id === 'brush_action') {
                                                                                                useEditorStore.getState().setBrushAction(next ? 'erase' : 'paint');
                                                                                            }
                                                                                             if (control.id === 'mesh_points_visibility') {
                                                                                                 useEditorStore.getState().setShowMeshPoints(next);
                                                                                             }
                                                                                        }}
                                                                                        className={cn(
                                                                                            "relative inline-flex h-5 w-10 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none",
                                                                                            (useEditorStore.getState().toolParameters[control.id] ?? control.default) ? 'bg-[#00a6ed]' : 'bg-slate-200'
                                                                                        )}
                                                                                    >
                                                                                        <span className={cn(
                                                                                            "pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out",
                                                                                            (useEditorStore.getState().toolParameters[control.id] ?? control.default) ? 'translate-x-5' : 'translate-x-0'
                                                                                        )} />
                                                                                    </button>
                                                                                </div>
                                                                            )}
                                                                        </div>
                                                                    ))}
                                                                </div>
                                                            )}
                                                        </div>
                                                    );
                                                }

                                                // Image Grid Layout (Matches UI exactly: 3 cols)
                                                return (
                                                    <button
                                                        key={tool.id}
                                                        onClick={() => {
                                                            setActiveTool(tool.id);
                                                            const state = useEditorStore.getState();
                                                            if (tool.id !== activeTool) {
                                                                state.clearBrushStrokes();
                                                            }
                                                            state.setBrushMode(!!tool.brushEnabled);
                                                            const defaults = buildToolDefaults(tool);
                                                            state.setToolParameters(defaults);
                                                            state.setBrushAction(Boolean(defaults.brush_action) ? 'erase' : 'paint');
                                                        }}
                                                        className="relative group flex flex-col items-center flex-1"
                                                    >
                                                        <div className={cn(
                                                            "w-full aspect-[3/4] rounded-lg overflow-hidden mb-2 relative transition-all",
                                                            isSelected ? "ring-[3px] ring-[#00a6ed] ring-offset-2" : "ring-1 ring-slate-200"
                                                        )}>
                                                            {tool.image ? (
                                                                <img src={tool.image} alt={tool.label} className="w-full h-full object-cover" />
                                                            ) : (
                                                                <div className="w-full h-full bg-slate-100 flex items-center justify-center"><User size={24} className="text-slate-300" /></div>
                                                            )}
                                                            {/* Empty circle top right like image */}
                                                            <div className="absolute top-1.5 right-1.5 w-4 h-4 rounded-full bg-black/20 border-2 border-white backdrop-blur-sm z-10 hidden group-hover:block" />
                                                            {isSelected && <div className="absolute top-1.5 right-1.5 w-4 h-4 rounded-full bg-[#00a6ed] border-2 border-white z-10" />}
                                                        </div>
                                                        <span className="text-[12px] font-bold text-slate-700 text-center leading-tight">
                                                            {tool.label.replace('AI ', '')}
                                                        </span>
                                                    </button>
                                                );
                                            })}
                                        </div>
                                    </div>
                                ))}
                            </div>

                            {/* Action Buttons at bottom (Matches screenshot exactly) */}
                            {activeItem.id === 'portrait' && (
                                <div className="p-4 border-t border-slate-200 bg-white shrink-0">
                                    <button
                                        onClick={() => { }}
                                        className="w-full bg-slate-200/70 text-white font-bold py-2 rounded-full text-sm mb-3 cursor-not-allowed flex flex-col items-center justify-center group"
                                    >
                                        <span>Generate</span>
                                        <span className="text-[12px] font-medium opacity-80 mt-0.5">0 style(s) selected, 0 credit(s)</span>
                                    </button>
                                    <div className="flex items-center gap-3">
                                        <button className="flex-1 border border-slate-800 text-slate-800 font-bold py-[7px] rounded-full text-[13px] hover:bg-slate-50 transition-colors bg-white">
                                            Cancel
                                        </button>
                                        <button className="flex-1 bg-slate-200 text-white font-bold py-[7px] rounded-full text-[13px] cursor-not-allowed">
                                            Apply
                                        </button>
                                    </div>
                                </div>
                            )}

                            {activeTool && (
                                <div className="p-4 border-t border-slate-200 bg-white shrink-0 space-y-2">
                                    {(activeTool === 'background_replace' || activeTool === 'hairstyle') && (
                                        <button
                                            onClick={async () => {
                                                if (!sessionId) return;
                                                setProcessingStatus('processing');
                                                try {
                                                    const editingType = activeTool === 'hairstyle' ? 'detect_hair_mask' : 'detect_mask';
                                                    const response = await processImage(sessionId, editingType, {});
                                                    if (response.status === 'success' && response.data) {
                                                        const dataUrl = `data:image/png;base64,${response.data.result_image}`;
                                                        useEditorStore.getState().setOriginalMask(dataUrl);
                                                        setProcessingStatus('idle');
                                                    }
                                                } catch (e: any) {
                                                    setError(e.message || 'Detection failed');
                                                    setProcessingStatus('error');
                                                }
                                            }}
                                            disabled={processingStatus === 'processing' || !sessionId}
                                            className="w-full border-2 border-[#00a6ed] text-[#00a6ed] font-bold py-2.5 rounded-xl text-sm flex items-center justify-center gap-2 transition-colors hover:bg-blue-50 disabled:opacity-50 disabled:cursor-not-allowed"
                                        >
                                            {processingStatus === 'processing' ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
                                            <span>{activeTool === 'hairstyle' ? 'Detect Hair Mask' : 'Detect Mask'}</span>
                                        </button>
                                    )}
                                    {(activeTool) && (
                                        <button
                                            onClick={handleResetTool}
                                            className="w-full border-2 border-orange-400 text-orange-500 font-bold py-2.5 rounded-xl text-sm flex items-center justify-center gap-2 transition-colors hover:bg-orange-50"
                                        >
                                            <RotateCcw size={16} />
                                            <span>Reset Tool</span>
                                        </button>
                                    )}
                                    {activeTool === 'hair_transfer' ? (
                                        <button
                                            onClick={handleApplyHairTransfer}
                                            disabled={processingStatus === 'processing' || !sessionId || !hairTransferShapeFile || !hairTransferColorFile}
                                            className="w-full bg-[#00a6ed] text-white font-bold py-2.5 rounded-xl text-sm flex items-center justify-center gap-2 transition-colors hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                                        >
                                            {processingStatus === 'processing' ? <Loader2 size={16} className="animate-spin" /> : <ArrowLeftRight size={16} />}
                                            <span>{processingStatus === 'processing' ? 'Transferring...' : 'Run Hair Transfer'}</span>
                                        </button>
                                    ) : (
                                        <button
                                            onClick={handleApplyAIEditing}
                                            disabled={processingStatus === 'processing' || !sessionId || (activeItem.id === 'face-reshape' && Object.keys(useEditorStore.getState().toolParameters).length === 0)}
                                            className="w-full bg-[#00a6ed] text-white font-bold py-2.5 rounded-xl text-sm flex items-center justify-center gap-2 transition-colors hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                                        >
                                            {processingStatus === 'processing' ? <Loader2 size={16} className="animate-spin" /> : <Wand2 size={16} />}
                                            <span>{processingStatus === 'processing' ? 'Processing...' : 'Apply Tool'}</span>
                                        </button>
                                    )}
                                </div>
                            )}
                        </div>
                    );
                })()}
            </div>
        </div>
    );
};
