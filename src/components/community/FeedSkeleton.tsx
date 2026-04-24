import React from 'react';

export const FeedSkeleton: React.FC = () => {
    return (
        <div className="w-full max-w-lg mx-auto mb-6 bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm animate-pulse">
            <div className="flex items-center gap-3 p-4">
                <div className="w-10 h-10 rounded-full bg-slate-200"></div>
                <div className="space-y-2 flex-1">
                    <div className="h-4 bg-slate-200 rounded w-1/3"></div>
                    <div className="h-3 bg-slate-200 rounded w-1/4"></div>
                </div>
            </div>
            <div className="w-full aspect-square sm:aspect-[4/5] bg-slate-200"></div>
            <div className="p-4 space-y-3">
                <div className="flex gap-4">
                    <div className="w-6 h-6 rounded-full bg-slate-200"></div>
                    <div className="w-6 h-6 rounded-full bg-slate-200"></div>
                    <div className="w-6 h-6 rounded-full bg-slate-200"></div>
                </div>
                <div className="h-4 bg-slate-200 rounded w-1/4"></div>
                <div className="h-4 bg-slate-200 rounded w-full"></div>
            </div>
        </div>
    );
};

export const EmptyState: React.FC<{ message?: string; subMessage?: string }> = ({ 
    message = "No posts yet", 
    subMessage = "Be the first to share an Edit with the community!" 
}) => {
    return (
        <div className="flex flex-col items-center justify-center p-12 text-center h-full min-h-[400px]">
            <div className="w-20 h-20 rounded-full bg-blue-50 flex items-center justify-center text-blue-500 mb-4">
                <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
            </div>
            <h3 className="text-lg font-bold text-slate-800">{message}</h3>
            <p className="text-slate-500 mt-2 max-w-sm">{subMessage}</p>
        </div>
    );
};
