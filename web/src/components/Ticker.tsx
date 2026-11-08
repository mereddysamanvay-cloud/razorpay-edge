import { Identity } from './ui'

export interface TickerItem { id: string; name: string; sub?: string; logo?: string | null }

/** Continuous marquee; pauses on hover, scrolls manually, items are links when onPick is provided. */
export function Ticker({ items, label, onPick }: { items: TickerItem[]; label: string; onPick?: (id: string) => void }) {
  const row = [...items, ...items]
  return (
    <section aria-label={label}>
      <p className="label mb-2">{label}</p>
      <div className="ticker overflow-x-auto scroll-thin rounded-lg border border-line bg-white py-3" tabIndex={0}>
        <div className="ticker-track flex w-max gap-3 px-3">
          {row.map((it, i) => {
            const Tag = onPick ? 'button' : 'div'
            return (
              <Tag key={`${it.id}-${i}`} {...(onPick ? { onClick: () => onPick(it.id), type: 'button' as const } : {})}
                className="flex shrink-0 items-center gap-2.5 rounded-md border border-line bg-bg px-3 py-2 text-left hover:border-brand/50">
                <Identity name={it.name} logo={it.logo} size={28} />
                <span className="leading-tight">
                  <span className="block text-[13px] font-medium text-ink">{it.name}</span>
                  {it.sub && <span className="block text-[11px] text-mute">{it.sub}</span>}
                </span>
              </Tag>
            )
          })}
        </div>
      </div>
    </section>
  )
}

/** Fictional businesses for the pre-upload welcome screen. They are not Razorpay customers. */
export const ILLUSTRATIVE: TickerItem[] = [
  'Northwind Grocers', 'Lumen Fitness', 'Aster & Oak', 'Kite Learning', 'Marlow Travel', 'Pixel Pharmacy', 'Saffron Table', 'Orbit Electronics',
  'Fable Books', 'Juniper Home', 'Tidal Apparel', 'Cobalt Cloud', 'Meadow Gifts', 'Vantage Coaching',
].map((name, i) => ({ id: String(i), name, sub: 'Illustrative' }))
