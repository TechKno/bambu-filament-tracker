import { resolveColor } from '../colors.js'

// A reel seen face-on: the outer ring is the filament colour, the middle is the
// spool core. The grey outline keeps both black and white filament visible
// against the dark background.
export default function SpoolIcon({ color, size = 24 }) {
  const fill = resolveColor(color)
  const known = fill !== null
  const edge = 'rgba(154,163,178,.75)'

  return (
    <svg className="spool-icon" width={size} height={size} viewBox="0 0 24 24"
         role="img" aria-label={color ? `${color} filament` : 'filament'}>
      <title>{color || 'Unknown colour'}</title>
      <circle cx="12" cy="12" r="10.5" fill={known ? fill : 'var(--panel-2)'}
              stroke={edge} strokeWidth="1" />
      {!known && (
        <text x="12" y="9.5" textAnchor="middle" fontSize="7" fill="var(--muted)">?</text>
      )}
      <circle cx="12" cy="12" r="5" fill="var(--panel-2)" stroke={edge} strokeWidth="1" />
      <circle cx="12" cy="12" r="1.7" fill="rgba(0,0,0,.5)" stroke={edge} strokeWidth=".5" />
    </svg>
  )
}
