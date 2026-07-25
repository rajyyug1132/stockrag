import ReactMarkdown from 'react-markdown'

/** LLM answers come back as markdown (headings, bold, lists). Rendering them
 *  as plain text showed literal ## and ** on the Thesis briefing. */
export function Markdown({ text, dim = false }: { text: string; dim?: boolean }) {
  return (
    <div
      className={`text-sm leading-relaxed max-w-[72ch] space-y-3 ${dim ? 'text-ink-dim' : 'text-ink'}
        [&_h2]:text-xs [&_h2]:uppercase [&_h2]:tracking-kicker [&_h2]:text-ink-faint [&_h2]:mt-5
        [&_h3]:text-sm [&_h3]:font-medium [&_h3]:text-ink [&_h3]:mt-4
        [&_strong]:font-medium [&_strong]:text-ink
        [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-1.5
        [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:space-y-1.5`}
    >
      <ReactMarkdown>{text}</ReactMarkdown>
    </div>
  )
}
