import React from 'react';
import { Sidebar } from './Sidebar';
import { Canvas } from '../../features/editor/Canvas';
import { BottomBar } from './BottomBar';
import { useEditorStore } from '../../store/editorStore';
import UploadView from '../../views/UploadView';
import ErrorView from '../../views/ErrorView';
import SessionExpiredView from '../../views/SessionExpiredView';
import CommunityFeedView from '../../views/CommunityFeedView';
import MySharedPostsView from '../../views/MySharedPostsView';
import { StyleTransferView } from '../../views/StyleTransferView';
import { BackgroundReplaceView } from '../../views/BackgroundReplaceView';
import { InvisioDetectorView } from '../../views/InvisioDetectorView';
import { User, LayoutGrid } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';

export const Layout: React.FC = () => {
    const { currentView, activeTool } = useEditorStore();
    const { user, logout } = useAuthStore();
    const standaloneTools = new Set(['style-transfer', 'background_replace', 'detect-invisio-image']);
    const isCanvasVisible =
        !standaloneTools.has(activeTool ?? '') &&
        !['upload', 'error', 'session_expired', 'community', 'my_posts'].includes(currentView);

    /** Renders the main canvas area based on current view (MainLayout.render per LLD) */
    const renderMainContent = () => {
        // Intercept for standalone Style Transfer tool
        if (activeTool === 'style-transfer') {
            return <StyleTransferView />;
        }
        if (activeTool === 'background_replace') {
            return <BackgroundReplaceView />;
        }
        if (activeTool === 'detect-invisio-image') {
            return <InvisioDetectorView />;
        }

        switch (currentView) {
            case 'upload':
                return <UploadView />;
            case 'error':
                return <ErrorView />;
            case 'session_expired':
                return <SessionExpiredView />;
            case 'community':
                return <CommunityFeedView />;
            case 'my_posts':
                return <MySharedPostsView />;
            default:
                return <Canvas />;
        }
    };

    return (
        <div className="flex flex-col h-screen w-full bg-slate-50 overflow-hidden font-sans">
            {/* Top Navigation Bar */}
            <div className="h-[60px] bg-white border-b border-slate-200 flex items-center justify-between px-6 shrink-0 z-30">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded flex items-center justify-center overflow-hidden">
                        <div className="grid grid-cols-2 grid-rows-2 w-full h-full gap-0.5">
                            <div className="bg-pink-500 rounded-tl-[4px]"></div>
                            <div className="bg-teal-400 rounded-tr-[4px]"></div>
                            <div className="bg-indigo-500 rounded-bl-[4px]"></div>
                            <div className="bg-purple-600 rounded-br-[4px]"></div>
                        </div>
                    </div>
                    <span className="text-[22px] tracking-tight text-slate-900 flex items-center">
                        Invisio <span className="text-[#00a6ed] ml-1 font-light">Online Editor</span>
                    </span>
                </div>
                <div className="flex items-center gap-4 relative">


                    <div className="relative group flex items-center gap-2 cursor-pointer p-1 rounded-lg hover:bg-slate-100 transition-colors">
                        <div className="flex flex-col items-end">
                            <span className="text-[13px] font-bold text-slate-800 leading-tight">
                                {user?.username || 'User'}
                            </span>
                        </div>
                        <button className="w-8 h-8 bg-slate-800 rounded-full flex items-center justify-center text-white overflow-hidden shadow-sm">
                            <User size={16} />
                        </button>

                        {/* Dropdown Menu */}
                        <div className="absolute top-full right-0 mt-2 w-48 bg-white rounded-xl shadow-lg border border-slate-100 py-2 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
                            <button
                                onClick={() => useEditorStore.getState().setCurrentView('my_posts')}
                                className="w-full flex items-center gap-2 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 font-medium transition-colors"
                            >
                                <LayoutGrid size={16} /> My Shared Posts
                            </button>
                            <div className="h-px bg-slate-100 my-1"></div>
                            <button
                                onClick={logout}
                                className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 font-medium transition-colors"
                            >
                                Sign out
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <div className="flex flex-1 w-full overflow-hidden relative">
                {/* Left Sidebar */}
                <Sidebar />

                {/* Main Content Area */}
                <main className="flex-1 flex flex-col relative h-full bg-[#f4f6f8]">
                    <div className="flex-1 relative overflow-hidden bg-[#eef0f4] flex items-center justify-center p-8">
                        {renderMainContent()}
                    </div>

                    {/* Bottom Bar — only show when canvas is visible and contains tools like Download per user request */}
                    {isCanvasVisible && (
                        <BottomBar />
                    )}
                </main>
            </div>
        </div >
    );
};
