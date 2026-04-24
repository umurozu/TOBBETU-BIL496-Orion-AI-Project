/**
 * BrushOverlay — Canvas-based brush drawing tool (High Resolution)
 */

import React, { useRef, useEffect, useCallback, useState } from 'react';
import { useEditorStore } from '../../store/editorStore';

interface BrushOverlayProps {
    imageWidth: number; // Rendered width
    imageHeight: number; // Rendered height
    naturalWidth: number; // Original resolution width
    naturalHeight: number; // Original resolution height
}

const BrushOverlay: React.FC<BrushOverlayProps> = ({
    imageWidth,
    imageHeight,
    naturalWidth,
    naturalHeight,
}) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const cursorRef = useRef<HTMLDivElement>(null);
    const isDrawingRef = useRef(false);
    const lastPointRef = useRef<{ x: number; y: number } | null>(null);
    const currentStrokeRef = useRef<{ x: number; y: number }[]>([]);

    const {
        activeTool,
        brushSize,
        brushStrength,
        brushAction,
        brushStrokes,
        objectRemovalBrushStrokes,
        addBrushStroke,
    } = useEditorStore();

    const strokesForDisplay = activeTool === 'object_removal' ? objectRemovalBrushStrokes : brushStrokes;

    const [cursorPos, setCursorPos] = useState({ x: 0, y: 0 });
    const [showCursor, setShowCursor] = useState(false);

    // Scale from rendered to natural resolution
    const scaleX = naturalWidth / imageWidth;
    const scaleY = naturalHeight / imageHeight;

    const getCanvasPoint = useCallback(
        (e: React.MouseEvent<HTMLCanvasElement>) => {
            const canvas = canvasRef.current;
            if (!canvas) return null;
            const rect = canvas.getBoundingClientRect();
            return {
                x: e.clientX - rect.left,
                y: e.clientY - rect.top,
            };
        },
        []
    );

    const drawDot = useCallback(
        (ctx: CanvasRenderingContext2D, x: number, y: number) => {
            ctx.beginPath();
            ctx.arc(x, y, brushSize / 2, 0, Math.PI * 2);
            ctx.fill();
        },
        [brushSize]
    );

    const drawLine = useCallback(
        (
            ctx: CanvasRenderingContext2D,
            from: { x: number; y: number },
            to: { x: number; y: number }
        ) => {
            ctx.beginPath();
            ctx.moveTo(from.x, from.y);
            ctx.lineTo(to.x, to.y);
            ctx.stroke();
        },
        []
    );

    const setupBrushStyle = useCallback(
        (ctx: CanvasRenderingContext2D) => {
            const alpha = Math.max(0.25, brushStrength * 0.5);
            const color = brushAction === 'erase' ? `rgba(255, 59, 48, ${alpha})` : `rgba(0, 166, 237, ${alpha})`;
            
            ctx.fillStyle = color;
            ctx.strokeStyle = color;
            ctx.lineWidth = brushSize;
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';
        },
        [brushSize, brushStrength, brushAction]
    );

    const handleMouseDown = useCallback(
        (e: React.MouseEvent<HTMLCanvasElement>) => {
            const point = getCanvasPoint(e);
            if (!point) return;

            isDrawingRef.current = true;
            lastPointRef.current = point;
            
            // Store points in NATURAL resolution
            currentStrokeRef.current = [{ x: point.x * scaleX, y: point.y * scaleY }];

            const canvas = canvasRef.current;
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            if (!ctx) return;

            setupBrushStyle(ctx);
            drawDot(ctx, point.x, point.y);
        },
        [getCanvasPoint, setupBrushStyle, drawDot, scaleX, scaleY]
    );

    const handleMouseMove = useCallback(
        (e: React.MouseEvent<HTMLCanvasElement>) => {
            const point = getCanvasPoint(e);
            if (!point) return;

            setCursorPos(point);

            if (!isDrawingRef.current || !lastPointRef.current) return;

            const canvas = canvasRef.current;
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            if (!ctx) return;

            setupBrushStyle(ctx);
            drawLine(ctx, lastPointRef.current, point);
            drawDot(ctx, point.x, point.y);

            lastPointRef.current = point;
            currentStrokeRef.current.push({ x: point.x * scaleX, y: point.y * scaleY });
        },
        [getCanvasPoint, setupBrushStyle, drawLine, drawDot, scaleX, scaleY]
    );

    const updateMaskData = useCallback((latestStroke?: any) => {
        const state = useEditorStore.getState();
        const isObjectRemoval = state.activeTool === 'object_removal';
        const baseStrokes = isObjectRemoval ? state.objectRemovalBrushStrokes : state.brushStrokes;
        const setMask = isObjectRemoval ? state.setObjectRemovalMaskData : state.setMaskData;
        const originalMask = isObjectRemoval ? null : state.originalMask;

        const strokesToDraw = latestStroke ? [...baseStrokes, latestStroke] : baseStrokes;
        
        if (strokesToDraw.length === 0 && !originalMask) {
            setMask(null);
            return;
        }

        const canvas = document.createElement('canvas');
        // Use NATURAL resolution to prevent data loss
        canvas.width = naturalWidth;
        canvas.height = naturalHeight;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        ctx.fillStyle = 'black';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        if (originalMask) {
            const img = new Image();
            img.onload = () => {
                ctx.drawImage(img, 0, 0, naturalWidth, naturalHeight);
                drawStrokes(ctx, strokesToDraw);
                setMask(canvas.toDataURL('image/png'));
            };
            img.src = originalMask;
        } else {
            drawStrokes(ctx, strokesToDraw);
            setMask(canvas.toDataURL('image/png'));
        }
    }, [naturalWidth, naturalHeight]);

    const drawStrokes = (ctx: CanvasRenderingContext2D, strokes: any[]) => {
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';

        strokes.forEach((stroke) => {
            if (stroke.points.length === 0) return;
            // Scale brush size to natural resolution
            ctx.lineWidth = stroke.size * ((scaleX + scaleY) / 2);
            
            ctx.strokeStyle = stroke.action === 'erase' ? 'black' : 'white';
            ctx.fillStyle = stroke.action === 'erase' ? 'black' : 'white';
            
            ctx.beginPath();
            ctx.moveTo(stroke.points[0].x, stroke.points[0].y);
            
            if (stroke.points.length === 1) {
                ctx.arc(stroke.points[0].x, stroke.points[0].y, ctx.lineWidth / 2, 0, Math.PI * 2);
                ctx.fill();
            } else {
                for (let i = 1; i < stroke.points.length; i++) {
                    ctx.lineTo(stroke.points[i].x, stroke.points[i].y);
                }
                ctx.stroke();
            }
        });
    };

    const handleMouseUp = useCallback(() => {
        if (isDrawingRef.current && currentStrokeRef.current.length > 0) {
            const newStroke = {
                points: [...currentStrokeRef.current],
                size: brushSize,
                strength: brushStrength,
                action: brushAction,
            };
            addBrushStroke(newStroke);
            updateMaskData(newStroke);
        }

        isDrawingRef.current = false;
        lastPointRef.current = null;
        currentStrokeRef.current = [];
    }, [addBrushStroke, brushSize, brushStrength, brushAction, updateMaskData]);

    const handleMouseLeave = useCallback(() => {
        setShowCursor(false);
        if (isDrawingRef.current) {
            handleMouseUp();
        }
    }, [handleMouseUp]);

    const handleMouseEnter = useCallback(() => {
        setShowCursor(true);
    }, []);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        canvas.width = imageWidth;
        canvas.height = imageHeight;
        
        const ctx = canvas.getContext('2d');
        if (!ctx) return;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        strokesForDisplay.forEach(stroke => {
            const alpha = Math.max(0.25, stroke.strength * 0.5);
            const color = stroke.action === 'erase' ? `rgba(255, 59, 48, ${alpha})` : `rgba(0, 166, 237, ${alpha})`;
            
            ctx.fillStyle = color;
            ctx.strokeStyle = color;
            ctx.lineWidth = stroke.size;
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';

            if (stroke.points.length === 0) return;
            ctx.beginPath();
            // Scale natural points back to rendered space for display
            ctx.moveTo(stroke.points[0].x / scaleX, stroke.points[0].y / scaleY);
            
            if (stroke.points.length === 1) {
                ctx.arc(stroke.points[0].x / scaleX, stroke.points[0].y / scaleY, stroke.size / 2, 0, Math.PI * 2);
                ctx.fill();
            } else {
                for (let i = 1; i < stroke.points.length; i++) {
                    ctx.lineTo(stroke.points[i].x / scaleX, stroke.points[i].y / scaleY);
                }
                ctx.stroke();
            }
        });
        updateMaskData();
    }, [imageWidth, imageHeight, naturalWidth, naturalHeight, strokesForDisplay, updateMaskData, scaleX, scaleY]);

    return (
        <>
            <canvas
                ref={canvasRef}
                width={imageWidth}
                height={imageHeight}
                className="absolute inset-0 z-10"
                style={{ cursor: 'none' }}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseLeave}
                onMouseEnter={handleMouseEnter}
            />

            {showCursor && (
                <div
                    ref={cursorRef}
                    className="pointer-events-none absolute z-20"
                    style={{
                        left: cursorPos.x - brushSize / 2,
                        top: cursorPos.y - brushSize / 2,
                        width: brushSize,
                        height: brushSize,
                        borderRadius: '50%',
                        border: brushAction === 'erase' ? '2px solid rgba(255, 59, 48, 0.8)' : '2px solid rgba(0, 166, 237, 0.8)',
                        backgroundColor: brushAction === 'erase' ? `rgba(255, 59, 48, 0.2)` : `rgba(0, 166, 237, 0.2)`,
                    }}
                />
            )}
        </>
    );
};

export default BrushOverlay;
