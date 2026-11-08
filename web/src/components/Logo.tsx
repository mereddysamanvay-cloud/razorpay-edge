import { useState } from 'react'

export const LOGO_SRC = '/razorpay-edge-logo.webp'

// The supplied file is 2000 x 621 with blank margins. The wrapper shows only the region that holds the lockup
// (x 100-1900, y 175-460); the image itself is never edited, scaled non-uniformly or recoloured.
const VIEW = { x: 100, y: 175, w: 1800, h: 285, imgW: 2000 }

/** Renders the supplied logo file untouched. Never redrawn: if the file is missing, a plain notice is shown instead. */
export function Logo({ height = 40, showMissing = true }: { height?: number; showMissing?: boolean }) {
  const [missing, setMissing] = useState(false)
  if (missing) {
    return showMissing ? (
      <div className="rounded-md border border-dashed border-amber-400 bg-amber-50 px-3 py-2 text-[12px] text-amber-900">
        Logo file not found. Place the supplied image at <code className="font-semibold">web/public/razorpay-edge-logo.webp</code>.
      </div>
    ) : (
      <span className="text-[13px] font-semibold tracking-wide text-navy">RAZORPAY EDGE</span>
    )
  }
  return (
    <span className="relative block max-w-full overflow-hidden" style={{ width: Math.round((height * VIEW.w) / VIEW.h), aspectRatio: `${VIEW.w} / ${VIEW.h}` }} role="img" aria-label="Razorpay EDGE">
      <img src={LOGO_SRC} alt="" draggable={false} onError={() => setMissing(true)}
        style={{ position: 'absolute', maxWidth: 'none', width: `${(VIEW.imgW / VIEW.w) * 100}%`, left: `${-(VIEW.x / VIEW.w) * 100}%`, top: `${-(VIEW.y / VIEW.h) * 100}%` }} />
    </span>
  )
}

export const DESCRIPTOR = 'Merchant Relationship Intelligence'
export const TAGLINE = 'Find the signal. Make the move.'
