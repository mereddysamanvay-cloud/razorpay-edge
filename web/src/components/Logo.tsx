import { useState } from 'react'

export const LOGO_SRC = '/razorpay-edge-logo.png'

/** Renders the supplied logo file untouched. Never redrawn: if the file is missing, a plain notice is shown instead. */
export function Logo({ height = 40, showMissing = true }: { height?: number; showMissing?: boolean }) {
  const [missing, setMissing] = useState(false)
  if (missing) {
    return showMissing ? (
      <div className="rounded-md border border-dashed border-amber-400 bg-amber-50 px-3 py-2 text-[12px] text-amber-900">
        Logo file not found. Place the supplied image at <code className="font-semibold">web/public/razorpay-edge-logo.png</code>.
      </div>
    ) : (
      <span className="text-[13px] font-semibold tracking-wide text-navy">RAZORPAY EDGE</span>
    )
  }
  return <img src={LOGO_SRC} alt="Razorpay EDGE" onError={() => setMissing(true)} style={{ height, width: 'auto', objectFit: 'contain' }} />
}

export const DESCRIPTOR = 'Merchant Relationship Intelligence'
export const TAGLINE = 'Find the signal. Make the move.'
