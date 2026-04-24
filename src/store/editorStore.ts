import { create } from 'zustand';

/**
 * LLD View State Management
 * Tracks: session, image pipeline, processing status, errors, active view,
 * and brush tool state for interactive editing.
 */

export type AppView = 'upload' | 'editing' | 'preview' | 'download' | 'refinement' | 'community' | 'my_posts' | 'error' | 'session_expired';
export type ProcessingStatus = 'idle' | 'uploading' | 'processing' | 'completed' | 'error';

export interface BrushStroke {
    points: { x: number; y: number }[];
    size: number;
    strength: number;
    action: 'paint' | 'erase';
}

interface EditorState {
    // --- Core Editor State ---
    zoom: number;
    activeTool: string | null;
    activeSection: string; // 'home', 'portrait', 'edit', etc.
    uploadedImage: string | null;
    processedImage: string | null;
    compareMode: boolean;

    // --- Brush Tool State (LLD §3.1.1, RefinementTool) ---
    brushMode: boolean;
    brushSize: number;
    brushStrength: number;
    brushAction: 'paint' | 'erase';
    brushStrokes: BrushStroke[];
    objectRemovalBrushStrokes: BrushStroke[];

    // --- Session & Pipeline State (LLD §3.1.3) ---
    currentView: AppView;
    sessionId: string | null;
    imageId: string | null;
    resultId: string | null;
    processingStatus: ProcessingStatus;
    errorMessage: string | null;
    errorCode: string | null;

    // --- Mask Data (for backend processing) ---
    maskData: string | null;
    originalMask: string | null;
    objectRemovalMaskData: string | null;

    // --- Tool Parameters (for active editing tool) ---
    toolParameters: Record<string, unknown>;
    showMeshPoints: boolean;

    // --- Setters ---
    setZoom: (zoom: number) => void;
    setActiveTool: (tool: string | null) => void;
    setActiveSection: (section: string) => void;
    setUploadedImage: (url: string | null) => void;
    setProcessedImage: (url: string | null) => void;
    setCompareMode: (mode: boolean) => void;
    setBrushMode: (mode: boolean) => void;
    setBrushSize: (size: number) => void;
    setBrushStrength: (strength: number) => void;
    setBrushAction: (action: 'paint' | 'erase') => void;
    addBrushStroke: (stroke: BrushStroke) => void;
    undoBrushStroke: () => void;
    clearBrushStrokes: () => void;
    setMaskData: (data: string | null) => void;
    setOriginalMask: (data: string | null) => void;
    setObjectRemovalMaskData: (data: string | null) => void;
    setToolParameters: (params: Record<string, unknown>) => void;
    setShowMeshPoints: (show: boolean) => void;
    updateToolParameter: (key: string, value: unknown) => void;
    setCurrentView: (view: AppView) => void;
    setSessionId: (id: string | null) => void;
    setImageId: (id: string | null) => void;
    setResultId: (id: string | null) => void;
    setProcessingStatus: (status: ProcessingStatus) => void;
    setError: (message: string | null, code?: string | null) => void;
    clearError: () => void;
    revertToOriginal: () => void;
    resetSession: () => void;
    resetForNewUpload: () => void;
    resetLandmarks: () => void;
}

export const useEditorStore = create<EditorState>((set) => ({
    // Core
    zoom: 100,
    activeTool: null,
    activeSection: 'ai-editing',
    uploadedImage: null,
    processedImage: null,
    compareMode: false,

    // Brush
    brushMode: false,
    brushSize: 10,
    brushStrength: 1.0,
    brushAction: 'paint',
    brushStrokes: [],
    objectRemovalBrushStrokes: [],
    

    // Session & Pipeline
    currentView: 'upload',
    sessionId: null,
    imageId: null,
    resultId: null,
    processingStatus: 'idle',
    errorMessage: null,
    errorCode: null,

    // Mask Data
    maskData: null,
    originalMask: null,
    objectRemovalMaskData: null,

    // Tool Parameters
    toolParameters: {},
    showMeshPoints: true,

    // Core Setters
    setZoom: (zoom) => set({ zoom }),
    setActiveTool: (activeTool) => set({ activeTool }),
    setActiveSection: (activeSection) => set({ activeSection }),
    setUploadedImage: (uploadedImage) => set({ uploadedImage }),
    setProcessedImage: (processedImage) => set({ processedImage }),
    setCompareMode: (compareMode) => set({ compareMode }),

    // Brush Setters
    setBrushMode: (brushMode) => set({ brushMode }),
    setBrushSize: (brushSize) => set({ brushSize }),
    setBrushStrength: (brushStrength) => set({ brushStrength }),
    setBrushAction: (brushAction) => set({ brushAction }),
    addBrushStroke: (stroke) =>
        set((state) =>
            state.activeTool === 'object_removal'
                ? { objectRemovalBrushStrokes: [...state.objectRemovalBrushStrokes, stroke] }
                : { brushStrokes: [...state.brushStrokes, stroke] }
        ),
    undoBrushStroke: () =>
        set((state) =>
            state.activeTool === 'object_removal'
                ? { objectRemovalBrushStrokes: state.objectRemovalBrushStrokes.slice(0, -1) }
                : { brushStrokes: state.brushStrokes.slice(0, -1) }
        ),
    clearBrushStrokes: () =>
        set((state) =>
            state.activeTool === 'object_removal'
                ? { objectRemovalBrushStrokes: [], objectRemovalMaskData: null }
                : { brushStrokes: [], maskData: null, originalMask: null }
        ),
    setMaskData: (maskData) => set({ maskData }),
    setOriginalMask: (originalMask) => set({ originalMask }),
    setObjectRemovalMaskData: (objectRemovalMaskData) => set({ objectRemovalMaskData }),

    // Tool Parameters
    setToolParameters: (toolParameters) => set({ toolParameters }),
    setShowMeshPoints: (showMeshPoints) => set({ showMeshPoints }),
    updateToolParameter: (key, value) => set((state) => ({
        toolParameters: { ...state.toolParameters, [key]: value }
    })),

    // Session Setters
    setCurrentView: (currentView) => set({ currentView }),
    setSessionId: (sessionId) => set({ sessionId }),
    setImageId: (imageId) => set({ imageId }),
    setResultId: (resultId) => set({ resultId }),
    setProcessingStatus: (processingStatus) => set({ processingStatus }),
    setError: (errorMessage, errorCode = null) =>
        set({ errorMessage, errorCode, currentView: 'error' }),
    clearError: () => set({ errorMessage: null, errorCode: null }),
    revertToOriginal: () => set({
        processedImage: null,
        resultId: null,
        compareMode: false,
        processingStatus: 'idle',
        errorMessage: null,
    }),
    resetLandmarks: () => set((state) => ({
        toolParameters: { ...state.toolParameters, target_points: state.toolParameters.source_points }
    })),
    resetSession: () =>
        set({
            sessionId: null,
            imageId: null,
            resultId: null,
            uploadedImage: null,
            processedImage: null,
            processingStatus: 'idle',
            errorMessage: null,
            errorCode: null,
            maskData: null,
            originalMask: null,
            objectRemovalMaskData: null,
            currentView: 'upload',
            activeSection: 'ai-editing',
            activeTool: null,
            compareMode: false,
            brushMode: false,
            brushSize: 10,
            brushStrength: 1.0,
            brushStrokes: [],
            objectRemovalBrushStrokes: [],
            toolParameters: {},
        }),
    resetForNewUpload: () =>
        set({
            sessionId: null,
            imageId: null,
            resultId: null,
            processedImage: null,
            compareMode: false,
            processingStatus: 'idle',
            errorMessage: null,
            errorCode: null,
            maskData: null,
            originalMask: null,
            objectRemovalMaskData: null,
            brushMode: false,
            brushStrokes: [],
            objectRemovalBrushStrokes: [],
        }),
}));
