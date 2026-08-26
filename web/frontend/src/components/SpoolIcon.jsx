import { resolveColor, isTranslucent, toRgb } from '../colors.js'

// A filament colour swatch: a disc in the resolved colour with a surface-coloured
// core and a hairline ring, so both near-black and near-white filament read
// against either theme. Translucent filaments get a diagonal stripe fill rather
// than a flat one, so they don't look identical to their solid equivalent.
export default function SpoolIcon({ color, size = 24, title }) {
  const fill = resolveColor(color)
  const known = fill !== null
  const core = Math.max(4, Math.round(size * 0.36))

  let background = known ? fill : 'var(--s2)'
  if (known && isTranslucent(color)) {
    const [r, g, b] = toRgb(color) || [140, 140, 140]
    background = `repeating-linear-gradient(45deg, rgba(${r},${g},${b},.6) 0 3px, rgba(${r},${g},${b},.22) 3px 6px)`
  }

  return (
    <span
      className="spool-icon"
      title={title || color || 'Unknown colour'}
      style={{
        width: size, height: size, borderRadius: '50%', flex: 'none',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        background, border: '1px solid var(--line)',
      }}
    >
      <span style={{
        width: core, height: core, borderRadius: '50%',
        background: 'var(--s1)', border: '1px solid var(--line)',
      }} />
    </span>
  )
}
