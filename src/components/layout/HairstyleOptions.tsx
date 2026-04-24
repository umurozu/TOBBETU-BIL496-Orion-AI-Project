import React, { useEffect } from 'react';
import { Sparkles, SwatchBook } from 'lucide-react';
import { cn } from '../../lib/utils';
import {
    DEFAULT_HAIR_COLOR,
    HAIRSTYLE_COLOR_OPTIONS,
} from '../../config/hairstylePresets';

type HairstyleOptionsProps = {
    selectedColorId?: string | null;
    onSelectColorId: (colorId: string) => void;
};

export const HairstyleOptions: React.FC<HairstyleOptionsProps> = ({
    selectedColorId,
    onSelectColorId,
}) => {
    useEffect(() => {
        if (!selectedColorId) {
            onSelectColorId(DEFAULT_HAIR_COLOR);
        }
    }, [selectedColorId, onSelectColorId]);

    return (
        <div className="space-y-4 border-t border-slate-200 pt-4">
            <div className="rounded-2xl bg-blue-50/70 border border-blue-100 p-3">
                <div className="flex items-start gap-3">
                    <div className="w-9 h-9 rounded-xl bg-blue-100 text-[#00a6ed] flex items-center justify-center shrink-0">
                        <Sparkles size={16} />
                    </div>
                    <div>
                        <p className="text-[12px] font-bold text-slate-700">Hair Recolor</p>
                        <p className="text-[12px] text-slate-500 leading-relaxed mt-1">
                            Paint a rough hair mask, then the recolor assistant expands it across the full hair region before blending the new tone back naturally.
                        </p>
                    </div>
                </div>
            </div>

            <div className="space-y-3">
                <div className="flex items-center gap-2">
                    <SwatchBook size={14} className="text-amber-600" />
                    <p className="text-[12px] font-bold text-slate-700 uppercase tracking-wide">Hair Color</p>
                </div>
                <div className="grid grid-cols-1 gap-2">
                    {HAIRSTYLE_COLOR_OPTIONS.map((color) => {
                        const isSelected = selectedColorId === color.id;
                        return (
                            <button
                                key={color.id}
                                type="button"
                                onClick={() => onSelectColorId(color.id)}
                                className={cn(
                                    'flex items-center gap-3 rounded-xl border px-3 py-2 text-left transition-all bg-white',
                                    isSelected
                                        ? 'border-[#00a6ed] ring-2 ring-[#00a6ed]/15'
                                        : 'border-slate-200 hover:border-slate-300'
                                )}
                            >
                                <span
                                    className="w-8 h-8 rounded-full border border-black/10 shrink-0"
                                    style={{ backgroundColor: color.swatch }}
                                />
                                <span className="text-[12px] font-semibold text-slate-700">{color.label}</span>
                            </button>
                        );
                    })}
                </div>
            </div>
        </div>
    );
};
