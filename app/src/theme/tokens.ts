// GENERADO por app/scripts/generate-tokens.mjs desde docs/diseno/tokens.json. No editar a mano.
// Fuente: kit-zentheris-v3.2 (2026-11-02) · base-codigo/zentheris.tokens.json · versión 1.

/** Colores (tema oscuro único). Las referencias {z-color-…} ya están resueltas. */
export const colors = {
  "neutral-50": "#f3f7f5",
  "neutral-100": "#e1e9e5",
  "neutral-200": "#c5d2cd",
  "neutral-300": "#9fb3ad",
  "neutral-400": "#718c84",
  "neutral-500": "#4e6e66",
  "neutral-600": "#35544d",
  "neutral-700": "#244039",
  "neutral-800": "#162b25",
  "neutral-900": "#0d1f1a",
  "green-50": "#ecfdf5",
  "green-100": "#d1fae5",
  "green-200": "#a7f3d0",
  "green-300": "#86efac",
  "green-400": "#5dd39e",
  "green-500": "#4caf8e",
  "green-600": "#2f8a68",
  "green-700": "#1f6a50",
  "green-800": "#164d3c",
  "green-900": "#0d3228",
  "red-50": "#fef2f2",
  "red-100": "#fee2e2",
  "red-200": "#fecaca",
  "red-300": "#fca5a5",
  "red-400": "#f59099",
  "red-500": "#ef4444",
  "red-600": "#dc2626",
  "red-700": "#b91c1c",
  "red-800": "#7f1d1d",
  "red-900": "#2e1014",
  "yellow-50": "#fefce8",
  "yellow-100": "#fef9c3",
  "yellow-200": "#fef08a",
  "yellow-300": "#f59099",
  "yellow-400": "#facc15",
  "yellow-500": "#eab308",
  "yellow-600": "#ca8a04",
  "yellow-700": "#a16207",
  "yellow-800": "#6b4b06",
  "yellow-900": "#2b2305",
  "background-default": "#0d1f1a",
  "background-surface": "#162b25",
  "background-surfaceAlt": "#1a312a",
  "background-elevated": "#1f3b32",
  "background-overlay": "#00000080",
  "border-subtle": "#ffffff14",
  "border-medium": "#ffffff40",
  "border-strong": "#ffffff80",
  "border-accent": "#5dd39e",
  "border-error": "#ef4444",
  "border-warning": "#eab308",
  "text-primary": "#ffffff",
  "text-muted": "#c4d4cf",
  "text-disabled": "#5a7870",
  "text-inverse": "#0d1f1a",
  "text-accent": "#5dd39e",
  "text-accentSoft": "#86efac",
  "text-error": "#f59099",
  "text-warning": "#f59099",
  "text-success": "#86efac",
  "accent-primary": "#5dd39e",
  "accent-primaryHover": "#4caf8e",
  "accent-primaryActive": "#2f8a68",
  "accent-soft": "#163b30",
  "accent-secondary": "#86efac",
  "status-success-default": "#5dd39e",
  "status-success-bg": "#5dd39e14",
  "status-success-border": "#2f8a6866",
  "status-success-text": "#86efac",
  "status-warning-default": "#eab308",
  "status-warning-bg": "#f5909914",
  "status-warning-border": "#f590994d",
  "status-warning-text": "#f59099",
  "status-error-default": "#ef4444",
  "status-error-bg": "#f8717114",
  "status-error-border": "#f871714d",
  "status-error-text": "#f59099",
  "status-info-default": "#5dd39e",
  "status-info-bg": "#163b30",
  "status-info-border": "#5dd39e",
  "status-info-text": "#86efac",
  "state-hover-bg": "#5dd39e14",
  "state-active-bg": "#5dd39e24",
  "state-focus-ring": "#5dd39e",
  "state-selected-bg": "#5dd39e1f",
  "state-disabled-bg": "#244039",
  "state-disabled-text": "#5a7870",
  "state-disabled-border": "#ffffff0f",
  "chart-series1": "#5dd39e",
  "chart-series2": "#86efac",
  "chart-series3": "#f59099",
  "chart-series4": "#ef4444",
  "chart-series5": "#4caf8e",
  "chart-peak": "#F59099",
  "chart-grid": "#ffffff0f",
  "chart-label": "#c4d4cf"
} as const;

/** Espacios en dp (escala de 4 a 64). */
export const spacing = {
  "4": 4,
  "8": 8,
  "12": 12,
  "16": 16,
  "20": 20,
  "24": 24,
  "32": 32,
  "40": 40,
  "48": 48,
  "64": 64
} as const;

/** Radios en dp. */
export const radius = {
  "xs": 4,
  "sm": 8,
  "md": 10,
  "lg": 16,
  "xl": 20,
  "full": 9999
} as const;

/** Medidas de componentes y layout en dp (grid-columns sin unidad). */
export const sizes = {
  "bottomNav-height": 64,
  "topBar-height": 56,
  "button-height": 48,
  "iconButton-size": 36,
  "iconButtonLg-size": 48,
  "card-padding": 16,
  "screen-width": 402,
  "screen-minWidth": 375,
  "grid-columns": 4,
  "grid-gutter": 16,
  "grid-margin": 20
} as const;

/** Tamaños de letra primitivos en dp. Se usan los estilos de `typography`. */
export const fontSizes = {
  "display-xl": 32,
  "display-l": 28,
  "display-m": 20,
  "body-m": 16,
  "body-s": 14,
  "body-xs": 12,
  "ui-m": 16,
  "ui-s": 14,
  "data-xl": 36,
  "data-l": 24,
  "data-m": 20,
  "data-s": 12,
  "display-s": 16
} as const;

/** Pesos de letra. */
export const fontWeights = {
  "regular": "400",
  "medium": "500",
  "semibold": "600",
  "bold": "700"
} as const;

/** Interlineados de referencia (proporción). */
export const lineHeights = {
  "tight": 1.1,
  "snug": 1.15,
  "normal": 1.2,
  "relaxed": 1.4,
  "loose": 1.45
} as const;

/** Estilos de texto. `family` es el rol (display, body o data); `lineHeight` ya está en dp. */
export const typography = {
  "display-xl": {
    "family": "display",
    "fontSize": 32,
    "fontWeight": "700",
    "lineHeight": 35.2
  },
  "display-l": {
    "family": "display",
    "fontSize": 28,
    "fontWeight": "700",
    "lineHeight": 32.2
  },
  "display-l-24": {
    "family": "display",
    "fontSize": 24,
    "fontWeight": "700",
    "lineHeight": 27.6
  },
  "display-m": {
    "family": "display",
    "fontSize": 20,
    "fontWeight": "700",
    "lineHeight": 24
  },
  "display-s-16": {
    "family": "display",
    "fontSize": 16,
    "fontWeight": "700",
    "lineHeight": 20
  },
  "body-m-regular": {
    "family": "body",
    "fontSize": 16,
    "fontWeight": "400",
    "lineHeight": 23.2
  },
  "body-m-medium": {
    "family": "body",
    "fontSize": 16,
    "fontWeight": "500",
    "lineHeight": 23.2
  },
  "body-s-regular": {
    "family": "body",
    "fontSize": 14,
    "fontWeight": "400",
    "lineHeight": 19.6
  },
  "body-s-medium": {
    "family": "body",
    "fontSize": 14,
    "fontWeight": "500",
    "lineHeight": 19.6
  },
  "body-xs-regular": {
    "family": "body",
    "fontSize": 12,
    "fontWeight": "400",
    "lineHeight": 16.2
  },
  "body-xs-medium": {
    "family": "body",
    "fontSize": 12,
    "fontWeight": "500",
    "lineHeight": 16.2
  },
  "body-xs-regular-10": {
    "family": "body",
    "fontSize": 10,
    "fontWeight": "400",
    "lineHeight": 13
  },
  "body-xs-medium-10": {
    "family": "body",
    "fontSize": 10,
    "fontWeight": "500",
    "lineHeight": 13
  },
  "ui-m-semibold": {
    "family": "body",
    "fontSize": 16,
    "fontWeight": "600",
    "lineHeight": 20
  },
  "ui-s-semibold": {
    "family": "body",
    "fontSize": 14,
    "fontWeight": "600",
    "lineHeight": 16.8
  },
  "ui-s-semibold-12": {
    "family": "body",
    "fontSize": 12,
    "fontWeight": "600",
    "lineHeight": 14.4
  },
  "ui-s-etiqueta-12": {
    "family": "body",
    "fontSize": 12,
    "fontWeight": "600",
    "lineHeight": 14.4
  },
  "data-xl-32": {
    "family": "data",
    "fontSize": 32,
    "fontWeight": "700",
    "lineHeight": 32
  },
  "data-l": {
    "family": "data",
    "fontSize": 24,
    "fontWeight": "700",
    "lineHeight": 26.4
  },
  "data-m": {
    "family": "data",
    "fontSize": 20,
    "fontWeight": "700",
    "lineHeight": 23
  },
  "data-s-16": {
    "family": "data",
    "fontSize": 16,
    "fontWeight": "700"
  },
  "data-s": {
    "family": "data",
    "fontSize": 12,
    "fontWeight": "700"
  },
  "data-s-mono-regular-12": {
    "family": "data",
    "fontSize": 12,
    "fontWeight": "400"
  }
} as const;

export const fontFamilyRoles = {
  "display": "\"Satoshi\", \"Inter\", system-ui, sans-serif",
  "body": "\"Inter\", system-ui, sans-serif",
  "data": "\"JetBrains Mono\", ui-monospace, monospace"
} as const;
