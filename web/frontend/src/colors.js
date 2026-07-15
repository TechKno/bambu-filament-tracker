// Filament colours are free text ("Light Blue", "Olive Green", "Natural"), so we
// resolve a display colour in stages: a curated map of common filament names,
// then CSS named colours, then the last word ("Galaxy Purple" -> purple).
// Anything we can't resolve renders as a neutral "?" swatch rather than nothing.

const MAP = {
  // base colours (curated — CSS's own 'green'/'purple' are muddy at icon size)
  red: '#e03b3b', blue: '#2f6fd0', green: '#3fa551', yellow: '#f2c744',
  orange: '#f28c28', purple: '#8e5bd0', pink: '#f06fa8', brown: '#8b5a2b',
  magenta: '#d63aa8', violet: '#9457d6',

  // neutrals
  black: '#1a1a1a', 'matte black': '#141414', 'jet black': '#0a0a0a',
  white: '#f5f5f5', 'matte white': '#eeeeee',
  grey: '#9aa3b2', gray: '#9aa3b2', 'light grey': '#c3c9d4', 'light gray': '#c3c9d4',
  'dark grey': '#5a616e', 'dark gray': '#5a616e',
  silver: '#c0c4cc', natural: '#efe6d5', clear: '#dfe6ea', transparent: '#dfe6ea',
  cream: '#f3e9d2', ivory: '#f6f2e3', beige: '#e8d9b5', tan: '#d2b48c',

  // blues
  'light blue': '#7fb8e0', 'sky blue': '#6ec6f1', 'baby blue': '#a7d8f0',
  'dark blue': '#1b3a6b', 'royal blue': '#2b4fa2', navy: '#1f3a93',
  teal: '#008080', turquoise: '#40e0d0', cyan: '#00bcd4',

  // greens
  'light green': '#8bd17c', 'dark green': '#1f6b34', 'lime green': '#9ee34a',
  'olive green': '#6b7a2f', olive: '#808000', mint: '#8fe3c4', forest: '#228b22',
  glow: '#b7f77a', 'glow in the dark': '#b7f77a',

  // reds / warm
  'dark red': '#8b1a1a', burgundy: '#6d1a2e', maroon: '#7b1e2b',
  'hot pink': '#ff69b4', salmon: '#fa8072', coral: '#ff7f50',
  gold: '#d4af37', bronze: '#b08d57', copper: '#b87333',

  // specials
  wood: '#a97449', marble: '#e9e9e9',
  'carbon fibre': '#2b2b2b', 'carbon fiber': '#2b2b2b',
}

function cssSupports(value) {
  try {
    return typeof CSS !== 'undefined' && CSS.supports ? CSS.supports('color', value) : false
  } catch {
    return false
  }
}

/** True for see-through filaments, so the icon can be rendered semi-transparent
 *  (otherwise "Translucent Blue" would look identical to a solid "Blue"). */
export function isTranslucent(name) {
  return /\b(translucent|transparent|clear)\b/i.test(String(name || ''))
}

/** Return a CSS colour for a filament colour name, or null if unresolvable. */
export function resolveColor(name) {
  const n = String(name || '').trim().toLowerCase()
  if (!n) return null
  if (MAP[n]) return MAP[n]

  // "Light Blue" -> "lightblue" is a real CSS colour; so is "black", "red".
  const squashed = n.replace(/[\s_-]+/g, '')
  if (cssSupports(squashed)) return squashed
  if (cssSupports(n)) return n

  // Fall back to the most specific trailing word: "Galaxy Purple" -> purple.
  const words = n.split(/\s+/)
  for (let i = words.length - 1; i >= 0; i--) {
    if (MAP[words[i]]) return MAP[words[i]]
    if (cssSupports(words[i])) return words[i]
  }
  return null
}
