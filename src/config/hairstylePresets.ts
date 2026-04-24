export type LocalHairstylePreset = {
    id: string;
    label: string;
    description: string;
    image: string;
};

export type HairColorOption = {
    id: string;
    label: string;
    swatch: string;
};

export const HAIRSTYLE_PRESETS: LocalHairstylePreset[] = [
    {
        id: 'shape_01',
        label: 'Shape 1',
        description: 'Imported custom hairstyle reference with balanced crown volume.',
        image: '/hairstyles/shape-01.png',
    },
    {
        id: 'shape_02',
        label: 'Shape 2',
        description: 'Imported custom hairstyle reference with a fuller side silhouette.',
        image: '/hairstyles/shape-02.png',
    },
    {
        id: 'shape_03',
        label: 'Shape 3',
        description: 'Imported custom hairstyle reference with a tighter upper profile.',
        image: '/hairstyles/shape-03.png',
    },
    {
        id: 'shape_04',
        label: 'Shape 4',
        description: 'Imported custom hairstyle reference with a broader drape and longer falloff.',
        image: '/hairstyles/shape-04.png',
    },
];

export const HAIRSTYLE_COLOR_OPTIONS: HairColorOption[] = [
    { id: 'natural_black', label: 'Natural Black', swatch: '#1c1613' },
    { id: 'espresso_brown', label: 'Espresso Brown', swatch: '#402a1d' },
    { id: 'chestnut_brown', label: 'Chestnut Brown', swatch: '#744a30' },
    { id: 'honey_blonde', label: 'Honey Blonde', swatch: '#b79258' },
    { id: 'copper_red', label: 'Copper Red', swatch: '#a45330' },
];

export const DEFAULT_HAIRSTYLE_PRESET_ID = HAIRSTYLE_PRESETS[0].id;
export const DEFAULT_HAIR_COLOR = HAIRSTYLE_COLOR_OPTIONS[0].id;
