/**
 * Canvas — Image display component with brush overlay
 */

import React, { useRef, useState, useCallback } from 'react';
import { useEditorStore } from '../../store/editorStore';
import { Upload } from 'lucide-react';
import BrushOverlay from './BrushOverlay';
import { ScanningOverlay } from './ScanningOverlay';
import { FaceMeshOverlay } from './FaceMeshOverlay';

export const Canvas: React.FC = () => {
    const { uploadedImage, processedImage, compareMode, zoom, brushMode, processingStatus } = useEditorStore();
    const fileInputRef = useRef<HTMLInputElement>(null);
    const imgRef = useRef<HTMLImageElement>(null);
    const [isDragging, setIsDragging] = useState(false);
    const [imgDimensions, setImgDimensions] = useState({ 
        width: 0, 
        height: 0, 
        naturalWidth: 0, 
        naturalHeight: 0 
    });

    const setUploadedImage = useEditorStore((state) => state.setUploadedImage);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            const url = URL.createObjectURL(file);
            setUploadedImage(url);
        }
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
        const file = e.dataTransfer.files?.[0];
        if (file) {
            const url = URL.createObjectURL(file);
            setUploadedImage(url);
        }
    };

    const handleTriggerUpload = () => fileInputRef.current?.click();

    const handleImageLoad = useCallback(() => {
        if (imgRef.current) {
            setImgDimensions({
                width: imgRef.current.clientWidth,
                height: imgRef.current.clientHeight,
                naturalWidth: imgRef.current.naturalWidth,
                naturalHeight: imgRef.current.naturalHeight,
            });
        }
    }, []);

    if (!uploadedImage) {
        return (
            <div
                className={`w-[600px] h-[400px] border-2 border-dashed rounded-2xl flex flex-col items-center justify-center transition-colors
                    ${isDragging ? 'border-blue-500 bg-blue-50' : 'border-slate-300 bg-white hover:border-blue-400'}`}
                onDragOver={(e) => {
                    e.preventDefault();
                    setIsDragging(true);
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
                onClick={handleTriggerUpload}
            >
                <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    ref={fileInputRef}
                    onChange={handleFileChange}
                />
                <div className="w-16 h-16 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center mb-4">
                    <Upload className="w-8 h-8" />
                </div>
                <h3 className="text-xl font-semibold text-slate-800 mb-2">Upload an Image</h3>
                <p className="text-slate-500 mb-6">Drag & drop or click to upload</p>
                <button className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-full font-medium transition-colors shadow-lg shadow-blue-600/20">
                    Choose File
                </button>
            </div>
        );
    }

    const displayImage = processedImage && !compareMode ? processedImage : uploadedImage;

    if (compareMode && processedImage) {
        return (
            <div
                className="relative flex gap-4 shadow-2xl shadow-slate-300/50"
                style={{
                    transform: `scale(${zoom / 100})`,
                    transformOrigin: 'center center',
                    transition: 'transform 0.1s ease-out',
                }}
            >
                <div className="relative">
                    <div className="absolute top-2 left-2 bg-black/60 text-white text-xs font-medium px-2 py-1 rounded-md z-10">Original</div>
                    <img src={uploadedImage} alt="Original" className="max-h-[70vh] max-w-[38vw] object-contain block bg-white rounded-lg" />
                </div>
                <div className="relative">
                    <div className="absolute top-2 left-2 bg-blue-600/80 text-white text-xs font-medium px-2 py-1 rounded-md z-10">Processed</div>
                    <img src={processedImage} alt="Processed" className="max-h-[70vh] max-w-[38vw] object-contain block bg-white rounded-lg" />
                </div>
            </div>
        );
    }

    return (
        <div
            className="relative shadow-2xl shadow-slate-300/50"
            style={{
                transform: `scale(${zoom / 100})`,
                transformOrigin: 'center center',
                transition: 'transform 0.1s ease-out',
            }}
        >
            <img
                ref={imgRef}
                src={displayImage}
                alt="Image"
                className="max-h-[80vh] max-w-[80vw] object-contain block bg-white"
                onLoad={handleImageLoad}
            />

            {useEditorStore.getState().originalMask && brushMode && (
                <div className="absolute inset-0 pointer-events-none z-10 w-full h-full">
                    <img
                        src={useEditorStore.getState().originalMask || undefined}
                        alt="Auto-detected mask"
                        className="w-full h-full object-contain"
                        style={{
                            filter: 'invert(1) sepia(1) saturate(10) hue-rotate(320deg) opacity(0.25)',
                            mixBlendMode: 'multiply'
                        }}
                    />
                </div>
            )}

            {processingStatus === 'processing' && <ScanningOverlay />}

            {imgDimensions.width > 0 && (
                <FaceMeshOverlay 
                    imgWidth={imgDimensions.width} 
                    imgHeight={imgDimensions.height}
                />
            )}

            {brushMode && imgDimensions.width > 0 && (
                <BrushOverlay
                    imageWidth={imgDimensions.width}
                    imageHeight={imgDimensions.height}
                    naturalWidth={imgDimensions.naturalWidth}
                    naturalHeight={imgDimensions.naturalHeight}
                />
            )}

            {brushMode && (
                <div className="absolute top-3 right-3 z-30 flex items-center gap-2 bg-indigo-600/90 text-white text-xs font-semibold px-3 py-1.5 rounded-full shadow-lg">
                    <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
                    Brush Active
                </div>
            )}
        </div>
    );
};
