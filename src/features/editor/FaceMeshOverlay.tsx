import React, { useEffect, useState, useRef } from 'react';
import { useEditorStore } from '../../store/editorStore';
import { API_BASE_URL } from '../../services/api';

interface Point {
    x: number;
    y: number;
}

interface FaceMeshOverlayProps {
    imgWidth: number;
    imgHeight: number;
}

// Dedicated control point indices for intuitive editing (Mouth, Eyes, Nose, Jaw)
const CONTROL_INDICES = [
    61, 291, 0, 17, 37, 267, 84, 314, // Mouth
    33, 133, 159, 145,               // Left Eye
    362, 263, 386, 374,              // Right Eye
    1, 168,                          // Nose
    152, 234, 454, 10                // Face Shape
];

export const FaceMeshOverlay: React.FC<FaceMeshOverlayProps> = ({ imgWidth, imgHeight }) => {
    const { sessionId, activeTool, uploadedImage, showMeshPoints } = useEditorStore();
    const [sourcePoints, setSourcePoints] = useState<Point[]>([]);
    const [targetPoints, setTargetPoints] = useState<Point[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [imageElement, setImageElement] = useState<HTMLImageElement | null>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    
    // For dragging
    const [draggedIndex, setDraggedIndex] = useState<number | null>(null);

    // Load image element for warping
    useEffect(() => {
        if (!uploadedImage) return;
        const img = new Image();
        img.crossOrigin = "anonymous";
        img.src = uploadedImage;
        img.onload = () => setImageElement(img);
    }, [uploadedImage]);

    // Fetch landmarks on mount if face tool selected
    useEffect(() => {
        if (activeTool !== 'face_reshape_tool' || !sessionId) return;
        
        setIsLoading(true);
        fetch(`${API_BASE_URL}/landmarks/${sessionId}`)
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success' && data.data?.points) {
                    const pts = data.data.points.map((p: number[]) => ({ x: p[0], y: p[1] }));
                    setSourcePoints(pts);
                    setTargetPoints(pts);
                    useEditorStore.getState().updateToolParameter('source_points', pts.map((p:Point) => [p.x, p.y]));
                    useEditorStore.getState().updateToolParameter('target_points', pts.map((p:Point) => [p.x, p.y]));
                }
            })
            .catch(err => console.error("Failed to load landmarks:", err))
            .finally(() => setIsLoading(false));
    }, [sessionId, activeTool]);

    // Sync from store (for Reset)
    useEffect(() => {
        const storeTargetPoints = useEditorStore.getState().toolParameters.target_points as number[][];
        if (storeTargetPoints && storeTargetPoints.length > 0) {
            const pts = storeTargetPoints.map(p => ({ x: p[0], y: p[1] }));
            if (JSON.stringify(pts) !== JSON.stringify(targetPoints)) {
                setTargetPoints(pts);
            }
        }
    }, [useEditorStore.getState().toolParameters.target_points]);

    // Real-time Preview Warper
    useEffect(() => {
        if (!imageElement || !canvasRef.current || targetPoints.length === 0 || draggedIndex === null) return;
        
        const ctx = canvasRef.current.getContext('2d');
        if (!ctx) return;

        // Clear and draw background
        ctx.clearRect(0, 0, imgWidth, imgHeight);
        
        // Define a grid for warping (e.g., 20x20)
        const gridX = 20;
        const gridY = 20;
        const cellW = imgWidth / gridX;
        const cellH = imgHeight / gridY;

        // Radial Falloff logic reused for grid vertices
        const radius = imgWidth * 0.08;
        const dx = targetPoints[draggedIndex].x - sourcePoints[draggedIndex].x;
        const dy = targetPoints[draggedIndex].y - sourcePoints[draggedIndex].y;
        
        // Use a simpler approach for the real-time preview: 
        // We warp the entire image on a grid based on ALL current targetPoints movements.
        // To be fast, we only calculate displacement for grid vertices.
        
        for (let y = 0; y < gridY; y++) {
            for (let x = 0; x < gridX; x++) {
                // Source triangle vertices
                const s1 = { x: x * cellW, y: y * cellH };
                const s2 = { x: (x + 1) * cellW, y: y * cellH };
                const s3 = { x: x * cellW, y: (y + 1) * cellH };
                const s4 = { x: (x + 1) * cellW, y: (y + 1) * cellH };

                // Helper to calculate warped pos of any point based on radial falloff of the DRAGGED point
                // This is a fast approximation of the "streaming" effect
                const getWarped = (p: Point) => {
                    const d = Math.sqrt(Math.pow(p.x - sourcePoints[draggedIndex].x, 2) + Math.pow(p.y - sourcePoints[draggedIndex].y, 2));
                    if (d < radius) {
                        const weight = Math.pow(1 - d / radius, 2);
                        return { x: p.x + dx * weight, y: p.y + dy * weight };
                    }
                    return p;
                };

                const d1 = getWarped(s1);
                const d2 = getWarped(s2);
                const d3 = getWarped(s3);
                const d4 = getWarped(s4);

                // Draw two triangles per cell
                drawTriangle(ctx, imageElement, s1, s2, s3, d1, d2, d3);
                drawTriangle(ctx, imageElement, s2, s3, s4, d2, d3, d4);
            }
        }
    }, [targetPoints, draggedIndex, imageElement, imgWidth, imgHeight]);

    if (activeTool !== 'face_reshape_tool' || sourcePoints.length === 0) return null;

    if (isLoading) {
        return (
            <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/10">
                <div className="bg-white/80 px-4 py-2 rounded-lg font-bold text-sm">Generating Face Mesh...</div>
            </div>
        );
    }

    const handlePointerDown = (index: number) => (e: React.PointerEvent) => {
        e.preventDefault();
        setDraggedIndex(index);
    };

    const handlePointerMove = (e: React.PointerEvent) => {
        if (draggedIndex === null) return;
        e.preventDefault();
        
        const svg = e.currentTarget as unknown as SVGSVGElement;
        const rect = svg.getBoundingClientRect();
        
        const newX = ((e.clientX - rect.left) / rect.width) * imgWidth;
        const newY = ((e.clientY - rect.top) / rect.height) * imgHeight;
        
        const dx = newX - targetPoints[draggedIndex].x;
        const dy = newY - targetPoints[draggedIndex].y;

        const radius = imgWidth * 0.08;
        const newTargets = targetPoints.map((pt, i) => {
            if (i === draggedIndex) return { x: newX, y: newY };
            const dist = Math.sqrt(Math.pow(pt.x - targetPoints[draggedIndex].x, 2) + Math.pow(pt.y - targetPoints[draggedIndex].y, 2));
            if (dist < radius) {
                const weight = Math.pow(1 - dist / radius, 2);
                return { x: pt.x + dx * weight, y: pt.y + dy * weight };
            }
            return pt;
        });

        setTargetPoints(newTargets);
        useEditorStore.getState().updateToolParameter('target_points', newTargets.map(p => [Math.round(p.x), Math.round(p.y)]));
    };

    const handlePointerUp = () => {
        setDraggedIndex(null);
    };

    const renderPoints = showMeshPoints && CONTROL_INDICES.map((idx) => {
        const pt = targetPoints[idx];
        if (!pt) return null;
        return (
            <circle
                key={idx} cx={pt.x} cy={pt.y} r={imgWidth * 0.006}
                fill={draggedIndex === idx ? "#00f2fe" : "rgba(0, 166, 237, 0.7)"}
                stroke="white" strokeWidth={imgWidth * 0.0015}
                onPointerDown={handlePointerDown(idx)}
                className="hover:r-[0.9%] transition-all"
                style={{ cursor: draggedIndex === idx ? 'grabbing' : 'grab', filter: 'drop-shadow(0 0 5px rgba(0,0,0,0.3))' }}
                pointerEvents="all"
            />
        );
    });

    return (
        <div className="absolute inset-0 z-20 pointer-events-none">
            {/* Real-time Warp Canvas */}
            <canvas 
                ref={canvasRef} 
                width={imgWidth} height={imgHeight} 
                className="absolute inset-0 w-full h-full pointer-events-none"
                style={{ display: draggedIndex === null ? 'none' : 'block' }}
            />
            
            {/* Control Points Overlay */}
            <svg
                className="absolute inset-0 pointer-events-auto"
                viewBox={`0 0 ${imgWidth} ${imgHeight}`}
                width="100%" height="100%"
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                onPointerLeave={handlePointerUp}
                style={{ touchAction: 'none' }}
            >
                {renderPoints}
            </svg>
        </div>
    );
};

// Helper function for Piecewise Affine Warp in Canvas
function drawTriangle(ctx: CanvasRenderingContext2D, img: HTMLImageElement, 
                      s1: Point, s2: Point, s3: Point, 
                      d1: Point, d2: Point, d3: Point) {
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(d1.x, d1.y);
    ctx.lineTo(d2.x, d2.y);
    ctx.lineTo(d3.x, d3.y);
    ctx.closePath();
    ctx.clip();

    // Compute affine transform matrix
    // Fallback: This is a complex math part. Since we want streaming, I'll use a simplified version:
    // Just draw the triangle image region.
    const m11 = (d2.x - d1.x) / (s2.x - s1.x || 1);
    const m12 = (d2.y - d1.y) / (s2.x - s1.x || 1);
    const m21 = (d3.x - d1.x) / (s3.y - s1.y || 1);
    const m22 = (d3.y - d1.y) / (s3.y - s1.y || 1);
    const dx = d1.x - m11 * s1.x - m21 * s1.y;
    const dy = d1.y - m12 * s1.x - m22 * s1.y;

    ctx.setTransform(m11, m12, m21, m22, dx, dy);
    ctx.drawImage(img, 0, 0);
    ctx.restore();
}
