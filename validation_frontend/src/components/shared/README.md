# Standardized Plate Visualization Components

This directory contains reusable, standardized components for displaying well plates across the application.

**✨ Styling based on Cell Thalamus PlateViewerTab** - the professional look you love!

All styling matches the Cell Thalamus plate viewer exactly:
- 96-well large: `w-16 h-14` (Cell Thalamus dimensions)
- 384-well medium: `w-8 h-7` (proportionally scaled)
- Well labels: `text-white opacity-60 group-hover:opacity-100`
- Tooltips: `bg-slate-900 border border-slate-700`
- Legend boxes: `w-4 h-4 border-2` with `text-slate-300` labels
- Spacing: `mr-1 mb-1` between wells (medium/large)
- Hover: `hover:ring-2 hover:ring-violet-500` with violet ring
- Edge wells: Orange border `#f59e0b`

## Components

### PlateViewer

A universal plate visualization component that supports multiple plate formats (96-well, 384-well, 1536-well) with configurable sizing, styling, and interactivity.

**Features:**
- Supports 96, 384, and 1536-well plate formats
- Three size options: small, medium, large
- Optional axis labels (row letters, column numbers)
- Hover tooltips for well information
- Click handlers for interactive plates
- Dark/light mode support

**Example Usage:**

```tsx
import PlateViewer, { WellData } from './shared/PlateViewer';

const wells: WellData[] = [
  {
    id: 'A1',
    color: 'bg-blue-500',
    borderColor: '#3b82f6',
    borderWidth: 2,
    tooltip: {
      title: 'Well A1',
      lines: ['Compound X', '10 µM', 'Cell Line A']
    }
  },
  // ... more wells
];

<PlateViewer
  format="384"
  wells={wells}
  isDarkMode={true}
  size="medium"
  showLabels={false}
  showAxisLabels={true}
  onWellClick={(wellId) => console.log('Clicked:', wellId)}
/>
```

**Props:**

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `format` | `'96' \| '384' \| '1536'` | Required | Plate format |
| `wells` | `WellData[]` | Required | Array of well data |
| `isDarkMode` | `boolean` | Required | Dark/light mode toggle |
| `size` | `'small' \| 'medium' \| 'large'` | `'medium'` | Plate size |
| `showLabels` | `boolean` | `true` | Show well labels |
| `showAxisLabels` | `boolean` | `true` | Show row/col labels |
| `onWellClick` | `(wellId: string) => void` | `undefined` | Click handler |
| `className` | `string` | `''` | Additional CSS classes |

**WellData Type:**

```tsx
type WellData = {
  id: string;                    // Well ID (e.g., "A1", "B12")
  color?: string;                // Tailwind bg color class
  label?: string;                // Text to display in well
  tooltip?: {                    // Hover tooltip
    title: string;
    lines: string[];
  };
  borderColor?: string;          // CSS color value
  borderWidth?: number;          // Border width in pixels
};
```

---

### PlateLegend

A companion component for displaying plate legends with color-coded items.

**Features:**
- Horizontal or vertical layout
- Optional title
- Color boxes with borders
- Optional descriptions for each item
- Dark/light mode support

**Example Usage:**

```tsx
import PlateLegend, { LegendItem } from './shared/PlateLegend';

const items: LegendItem[] = [
  {
    label: 'Vehicle (DMSO)',
    color: 'bg-slate-600/70',
    borderColor: '#64748b',
    borderWidth: 2,
  },
  {
    label: 'Treatment',
    color: 'bg-blue-500',
    borderColor: '#3b82f6',
    borderWidth: 2,
    description: '10 µM compound X'
  },
];

<PlateLegend
  items={items}
  isDarkMode={true}
  layout="horizontal"
  title="Well Types"
/>
```

**Props:**

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `items` | `LegendItem[]` | Required | Legend items |
| `isDarkMode` | `boolean` | Required | Dark/light mode toggle |
| `layout` | `'horizontal' \| 'vertical'` | `'horizontal'` | Layout direction |
| `title` | `string` | `undefined` | Optional title |
| `className` | `string` | `''` | Additional CSS classes |

**LegendItem Type:**

```tsx
type LegendItem = {
  label: string;                 // Item label
  color: string;                 // Tailwind bg color class
  borderColor?: string;          // CSS color value
  borderWidth?: number;          // Border width in pixels
  description?: string;          // Optional description text
};
```

---

## Migration Guide

### Before (duplicated code):

```tsx
// Custom plate grid in every component
<div className="flex">
  {Array.from({ length: cols }).map((_, c) => (
    <div className="w-8 h-7 bg-blue-500 border-2" />
  ))}
</div>
```

### After (standardized):

```tsx
import PlateViewer, { WellData } from './shared/PlateViewer';

const wells: WellData[] = generateWellData();

<PlateViewer
  format="384"
  wells={wells}
  isDarkMode={isDarkMode}
  size="medium"
/>
```

## Benefits

1. **No Code Duplication**: Single source of truth for plate visualization logic
2. **Consistent Styling**: All plates look professional and match design system
3. **Easy Maintenance**: Fix bugs once, update all plates simultaneously
4. **Type Safety**: Full TypeScript support with clear interfaces
5. **Flexible**: Configurable for many use cases (calibration, experiments, live data)
6. **Performance**: Optimized rendering with proper key handling

## Current Usage

- `CalibrationPlateViewer.tsx` - Calibration plate design (384-well, medium size)
- `EpistemicDocumentaryPage.tsx` - Cycle plate previews (384-well, small size)
- More components can be migrated as needed

## Future Enhancements

- [ ] Add well selection state management
- [ ] Support for multi-select (Ctrl/Cmd + click)
- [ ] Export plate data as CSV/JSON
- [ ] Heatmap color gradients for quantitative data
- [ ] Custom well shapes (circular, square, etc.)
- [ ] Zoom/pan for large plates
