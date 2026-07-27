Transform the HTML/CSS/JS in my message into a React component that follows the project's patterns exactly.

## Rules to follow

**Framework**
- Next.js App Router, React 19, TypeScript
- Add `"use client"` only if the component uses state, effects, event handlers, or browser APIs
- Default to server components (no directive) for static/presentational UI

**Styling — translate ALL CSS to Tailwind v4 utility classes**
- Replace every CSS property with its Tailwind equivalent
- Use the zinc scale for neutrals (zinc-950 page bg, zinc-900 cards, zinc-800 inputs, zinc-700 secondary)
- Primary action color: blue-600 / hover:blue-500
- Status colors use `bg-{color}-900/50 text-{color}-300` pattern
- NO inline `style={{}}` props — everything in className
- NO CSS modules, NO styled-components, NO emotion
- Use `cn()` from `@/lib/utils` when combining conditional classes

**Class conventions**
- Cards: `bg-zinc-900 border border-zinc-800 rounded-xl p-5`
- Inputs: `bg-zinc-800 border border-zinc-700 text-white px-3 py-2.5 rounded-lg focus:border-blue-500 outline-none text-sm`
- Primary button: `bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-4 py-2.5 rounded-lg font-medium text-sm transition-colors`
- Secondary button: `bg-zinc-700 hover:bg-zinc-600 text-white px-4 py-2 rounded-lg text-sm transition-colors`
- Ghost/link button: `text-zinc-400 hover:text-white text-sm transition-colors`
- All interactive elements need `transition-colors`
- Disabled states: `disabled:opacity-50`
- `shrink-0` not `flex-shrink-0`

**TypeScript**
- Define a `Props` interface for every component that accepts props
- No `any` — use `unknown` and narrow it
- Event handlers: `React.FormEvent`, `React.ChangeEvent<HTMLInputElement>`, etc.

**JavaScript → React**
- `document.querySelector` → `useRef<HTMLElement>(null)` + `.current`
- `addEventListener` → inline event handlers (`onClick`, `onChange`, etc.)
- `fetch()` calls → import and use the `api` client from `@/lib/api`
- `localStorage` → only in `useEffect` (client-side guard)
- `classList.add/remove` → conditional className with state
- `innerHTML` → JSX children or `dangerouslySetInnerHTML` (only if HTML is sanitized)

**Structure**
- One component per file
- Named export (not default) for shared components in `src/components/ui/`
- Default export for page-level components in `src/app/`
- Props destructured in function signature
- Keep JSX readable — extract complex repeated blocks into sub-components or variables

**Icons**
- Replace any icon fonts (Font Awesome, Material Icons, etc.) with Lucide React equivalents
- Import: `import { IconName } from "lucide-react"`
- Size: `className="size-4"` in buttons, `className="size-5"` standalone

**Loading states**
- Show skeleton: `<div className="h-{n} bg-zinc-800 rounded-xl animate-pulse" />`
- Disable + show spinner text on async buttons: `disabled={loading}` + `{loading ? "Saving…" : "Save"}`

**DO NOT**
- Do not add comments explaining what the code does
- Do not use `React.FC` — use plain function declarations
- Do not wrap in extra `<div>` unless layout requires it
- Do not invent props that weren't in the original HTML
- Do not use shadcn component imports in page files — raw Tailwind only in pages

## Output format

Output ONLY the component file content. No explanation before or after. No markdown fences. Start with the import lines and end with the export.

If the HTML has multiple distinct logical sections, split them into a primary component + small sub-components in the same file.
