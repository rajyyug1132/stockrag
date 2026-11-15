/** Disclosure arrow for <summary>; the parent <details> needs `group`.
 *  Drawn as SVG so it does not depend on which font supplies the glyph. */
export function Chevron() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 12 12"
      className="w-3 h-3 shrink-0 text-ink-faint transition-transform group-open:rotate-90"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
    >
      <path d="M4.5 2.5 8 6l-3.5 3.5" />
    </svg>
  )
}
