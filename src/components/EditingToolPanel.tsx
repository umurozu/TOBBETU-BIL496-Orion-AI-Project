/**
 * EditingToolPanel — Reusable Brush/Slider/Parameter Panel
 *
 * Provides interactive controls for AI editing tabs that need
 * brush-based input or adjustable parameters.
 *
 * This component is designed to be embedded inside each editing tab's
 * expanded content area. It renders:
 *   - Brush size slider (with +/- buttons)
 *   - Brush strength/opacity slider
 *   - Custom parameter sliders (dynamic, per-tool)
 *   - Toggle switches (e.g., strand enhancement on/off)
 *
 * Pattern:
 *   Each editing tab can define a `tools` config that maps to
 *   this panel's controls. When the user adjusts parameters,
 *   they are passed back via `onParametersChange` callback.
 *
 * Usage:
 *   <EditingToolPanel
 *     tools={[
 *       { id: 'smoothing', label: 'Smoothing', type: 'slider', min: 0, max: 1, step: 0.1, default: 0.5 },
 *       { id: 'strand_enhancement', label: 'Strand Enhancement', type: 'toggle', default: true },
 *     ]}
 *     brushEnabled={true}
 *     onParametersChange={(params) => console.log(params)}
 *   />
 */

import { useState, useEffect, useCallback } from 'react';
import {
    Paintbrush,
    Minus,
    Plus,
    ToggleLeft,
    ToggleRight,
} from 'lucide-react';

/* ------------------------------------------------------------------ */
/*  Tool Config Types                                                  */
/* ------------------------------------------------------------------ */

export interface SliderToolConfig {
    id: string;
    label: string;
    type: 'slider';
    min: number;
    max: number;
    step: number;
    default: number;
    unit?: string;
    icon?: React.ReactNode;
}

export interface ToggleToolConfig {
    id: string;
    label: string;
    type: 'toggle';
    default: boolean;
    icon?: React.ReactNode;
}

export type ToolConfig = SliderToolConfig | ToggleToolConfig;

export interface EditingToolPanelProps {
    /** Tool definitions — sliders, toggles, etc. */
    tools: ToolConfig[];
    /** Whether to show brush size/strength controls */
    brushEnabled?: boolean;
    /** Default brush size in pixels */
    defaultBrushSize?: number;
    /** Default brush strength (0-1) */
    defaultBrushStrength?: number;
    /** Callback when any parameter changes */
    onParametersChange?: (params: Record<string, unknown>) => void;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function EditingToolPanel({
    tools,
    brushEnabled = false,
    defaultBrushSize = 10,
    defaultBrushStrength = 1.0,
    onParametersChange,
}: EditingToolPanelProps) {
    // Brush state
    const [brushSize, setBrushSize] = useState(defaultBrushSize);
    const [brushStrength, setBrushStrength] = useState(defaultBrushStrength);

    // Dynamic tool values
    const [toolValues, setToolValues] = useState<Record<string, unknown>>(() => {
        const initial: Record<string, unknown> = {};
        tools.forEach((tool) => {
            initial[tool.id] = tool.default;
        });
        return initial;
    });

    // Emit parameter changes
    const emitChanges = useCallback(() => {
        if (!onParametersChange) return;

        const params: Record<string, unknown> = { ...toolValues };
        if (brushEnabled) {
            params.brush_size = brushSize;
            params.brush_strength = brushStrength;
        }
        onParametersChange(params);
    }, [toolValues, brushSize, brushStrength, brushEnabled, onParametersChange]);

    useEffect(() => {
        emitChanges();
    }, [emitChanges]);

    const updateToolValue = (id: string, value: unknown) => {
        setToolValues((prev) => ({ ...prev, [id]: value }));
    };

    return (
        <div className="flex flex-col gap-3">
            {/* Brush Controls */}
            {brushEnabled && (
                <>
                    {/* Brush Size */}
                    <div className="bg-white/5 rounded-xl p-3">
                        <div className="flex items-center gap-2 mb-2">
                            <Paintbrush className="w-4 h-4 text-white/50" />
                            <span className="text-white/70 text-xs font-medium">
                                Brush Size
                            </span>
                            <span className="ml-auto text-white/50 text-xs">
                                {brushSize}px
                            </span>
                        </div>
                        <div className="flex items-center gap-2">
                            <button
                                onClick={() =>
                                    setBrushSize(Math.max(1, brushSize - 2))
                                }
                                className="p-1 rounded bg-white/10 hover:bg-white/20 transition-colors"
                            >
                                <Minus className="w-3 h-3 text-white/70" />
                            </button>
                            <input
                                type="range"
                                min="1"
                                max="50"
                                value={brushSize}
                                onChange={(e) =>
                                    setBrushSize(Number(e.target.value))
                                }
                                className="flex-1 h-1 bg-white/20 rounded-lg appearance-none cursor-pointer accent-blue-500"
                            />
                            <button
                                onClick={() =>
                                    setBrushSize(Math.min(50, brushSize + 2))
                                }
                                className="p-1 rounded bg-white/10 hover:bg-white/20 transition-colors"
                            >
                                <Plus className="w-3 h-3 text-white/70" />
                            </button>
                        </div>
                    </div>

                    {/* Brush Strength */}
                    <div className="bg-white/5 rounded-xl p-3">
                        <div className="flex items-center gap-2 mb-2">
                            <Paintbrush className="w-4 h-4 text-white/50" />
                            <span className="text-white/70 text-xs font-medium">
                                Brush Strength
                            </span>
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
                            onChange={(e) =>
                                setBrushStrength(Number(e.target.value))
                            }
                            className="w-full h-1 bg-white/20 rounded-lg appearance-none cursor-pointer accent-blue-500"
                        />
                    </div>
                </>
            )}

            {/* Dynamic Tool Controls */}
            {tools.map((tool) => {
                if (tool.type === 'slider') {
                    const sliderTool = tool as SliderToolConfig;
                    const currentValue = (toolValues[tool.id] as number) ?? sliderTool.default;

                    return (
                        <div key={tool.id} className="bg-white/5 rounded-xl p-3">
                            <div className="flex items-center gap-2 mb-2">
                                {sliderTool.icon || (
                                    <div className="w-4 h-4 rounded-full bg-gradient-to-r from-blue-400 to-purple-400" />
                                )}
                                <span className="text-white/70 text-xs font-medium">
                                    {sliderTool.label}
                                </span>
                                <span className="ml-auto text-white/50 text-xs">
                                    {sliderTool.unit === '%'
                                        ? `${Math.round(currentValue * 100)}%`
                                        : currentValue.toFixed(1)}
                                </span>
                            </div>
                            <input
                                type="range"
                                min={sliderTool.min}
                                max={sliderTool.max}
                                step={sliderTool.step}
                                value={currentValue}
                                onChange={(e) =>
                                    updateToolValue(tool.id, Number(e.target.value))
                                }
                                className="w-full h-1 bg-white/20 rounded-lg appearance-none cursor-pointer accent-purple-500"
                            />
                        </div>
                    );
                }

                if (tool.type === 'toggle') {
                    const toggleTool = tool as ToggleToolConfig;
                    const isOn = (toolValues[tool.id] as boolean) ?? toggleTool.default;

                    return (
                        <button
                            key={tool.id}
                            onClick={() => updateToolValue(tool.id, !isOn)}
                            className="flex items-center gap-3 bg-white/5 rounded-xl p-3 hover:bg-white/10 transition-colors w-full"
                        >
                            {toggleTool.icon || (
                                <div className="w-4 h-4 rounded-full bg-gradient-to-r from-green-400 to-emerald-400" />
                            )}
                            <span className="text-white/70 text-xs font-medium flex-1 text-left">
                                {toggleTool.label}
                            </span>
                            {isOn ? (
                                <ToggleRight className="w-6 h-6 text-blue-400" />
                            ) : (
                                <ToggleLeft className="w-6 h-6 text-white/30" />
                            )}
                        </button>
                    );
                }

                return null;
            })}
        </div>
    );
}
