# Clausewise — Plays

**What it is:** a contract clause risk analyzer. Upload a PDF or DOCX and every risky
clause comes back with a severity, a plain-English reason, a suggested rewrite, and a
citation into the exact words it came from — click a finding and the contract pane scrolls
to and highlights the source. If the model cannot quote what it is flagging, the finding is
**dropped** rather than shown with an approximate source, and the count of what was dropped
is on screen.
**Stage:** live. API on Fly (`clausewise-api.fly.dev`, single machine), web on Vercel
(`<fill in the production URL>`). Next.js 16 / React 19 / Tailwind v4 + FastAPI / Python 3.12,
Anthropic primary with Groq failover. 87 API tests, 16 web tests.

**Through-line (shared across my products):** grounded, honest AI that shows its work.
Verdkt proves a strategy wrong before real money; Orviqo asks before it embarrasses your
customer; Trajekt ties every stage to the real CV; Clausewise refuses to tell a lawyer
something it cannot point at. Same brand, four markets. **This is the moat and the story.**

**Honest framing:** Clausewise was built as **proof of work, not as a business.** The career
play is the point; the product play is a genuine option that has not been validated and
should not be built on faith. Do not let the product section flatter you into shipping
features nobody has paid for.

**How to use:** from this repo's Claude Code session, say "run the career play"
(or "product play" / "audience play"). Read that section, do the next unchecked step, then
update its Status line. Keep it honest: only tick a box for work that actually shipped.

---

## Career play

**Why this exists.** Three live targets at once — **Genie AI** (Agentic Engineer, remote),
**Lawhive** (Ashby board), **Robin AI** (Anthropic partner). All three build contract-review
copilots. Cold outreach that leads with a working link beats one that leads with a promise.

**The story it tells.** "I understand your core loop: retrieve the relevant clause, reason
over it, stay grounded in the source so a lawyer can verify rather than trust." That is the
whole job description at those companies, demonstrated rather than claimed.

**Positioning line.** "I build document AI that refuses to say what it can't prove."

**The three things to lead with — in this order.**

1. **The grounding gate.** Every finding must locate its quote in the clause it claims to
   describe, tolerating PDF line-wrap and nothing else. No span, no finding. The UI reports
   the drop count. *This is the differentiator* — it costs recall and buys the only thing
   that makes the tool usable by someone with professional liability on the line.
2. **The LLM-as-judge severity pass.** A second, independent call re-scores each finding
   from the clause alone, without seeing the first model's reasoning. Disagreement is
   **shown, not averaged away**. This directly mirrors Genie's LLM-as-judge evaluation work.
3. **The eval harness.** Precision 0.70 / recall 0.94 / F1 0.80, severity agreement 75%
   (12/16), 0 dropped as ungrounded, on 2 hand-labelled contracts. Small and synthetic —
   *say so first*, because volunteering the limitation is the credibility move. Most
   candidates have no eval at all.

**Engineering ammo beyond the demo.** Schema-enforced structured output on every provider
(no JSON repair path anywhere); narrow provider failover where only a dead account advances
the chain and a bad request fails loudly on the primary; a 429 misclassified as exhausted
credit that cost 5 of 13 clauses until status was checked before message; two layouts rather
than one that shrinks. All real decisions with reasons, which is what a senior interview
actually probes.

**Where to deploy.** Cold outreach to the three targets (link, not attachment). Portfolio
`/work/clausewise`. The repo README is the case study — it already reads as one.

**Next steps.**
- [ ] Record the 60-second Loom: upload the 2-page sample, click a finding, land on the
      source, mention the judge pass and the drop count
- [ ] Fill in the live URL above and check both links from a fresh browser
- [ ] Cold outreach to Genie AI, Lawhive, Robin AI — link the demo and the repo in the DM
- [ ] Portfolio case study at `/work/clausewise`, leading with the grounding gate
- [ ] Rehearse the honest answer to "how good is it really?" — the eval numbers *and* why
      they are directional

**Status:** _live and working; Loom not recorded, outreach not sent_

---

## Product play

**Read this section sceptically.** The demo works; that is not evidence anyone will pay.

**Possible thesis.** Contract review is priced for people who can afford lawyers. The
underserved buyer is the one signing *without* one — freelancer, contractor, small agency,
first-time founder — who currently either signs blind or pays £300 for an hour of review
they cannot afford to repeat.

**Why the incumbents leave that gap.** Genie, Robin, Luminance, Spellbook and LegalOn all
sell to law firms and in-house legal teams. Their pricing, onboarding and trust model are
built for that buyer. Serving a freelancer signing one contract a quarter is a different
product, not a smaller version of theirs.

**Why it might still be a bad business.** Frequency. Someone signs a handful of contracts a
year, which is the wrong shape for a subscription and a brutal shape for CAC. The moment of
need is sharp and rare — which favours pay-per-use, which favours a low ceiling. **This is
the objection to kill first, before writing any feature code.**

**The cheapest test that would change my mind.** Not a build. Put the existing demo behind a
"£9 to review this contract" payment intent, post it once where freelancers actually are,
and count who reaches for a card. Ten payers from one post is a signal; a hundred people
saying "great idea" is not.

**If it validated, the wedge → expansion.**
- Wedge: one contract, one plain-English answer, every claim clickable.
- Then: a clause precedent library ("this indemnity is harsher than your standard"), which
  is the actual defensible asset — comparison against *your* history, not a generic rubric.
- Then: redlines applied in-document, multi-contract diffing.

**What would have to be true first.** Real (not synthetic) eval contracts, because
precision on hand-written samples proves nothing about real agreements. Persistent storage
and auth — currently results die on deploy. And a defensible answer to "is this legal
advice?", which is a regulatory question, not a product one.

**Next steps.**
- [ ] Do not build. Run the £9 payment-intent test first
- [ ] Get 5-10 real contracts (under NDA) and re-run the eval against them
- [ ] Only if both land: persistence, auth, and a precedent-library spike

**Status:** _not started, and deliberately so — the career play comes first_

---

## Audience play

**Narrative.** "I built a contract AI that deletes its own findings when it can't quote
them." The refusal is the hook. Everyone is shipping AI that sounds confident; almost nobody
is shipping AI that visibly declines to answer.

**Hooks.**
- "My contract analyzer threw away 1 of its 8 findings. That's the feature."
- "Every AI legal tool tells you what's risky. Mine shows you the sentence, or shuts up."
- "I asked two different models to score the same clause. They disagreed on 4 of 15. I show
  you the disagreement instead of averaging it away."
- "A rate limit cost me 5 of 13 clauses because I read the error message before the status
  code."

**Angles.** The grounding gate as a product principle, not a technical detail. Judge-pass
disagreement as an honesty surface. The eval numbers *with* the caveats stated first — that
post writes itself and almost nobody does it. The Grok-versus-Groq key mix-up as a short,
funny, genuinely useful one.

**Channels + cadence.** LinkedIn and X, aimed at the legal-tech and AI-engineering crowd.
This is a burst, not a drumbeat: 3-4 posts around the Loom and the outreach, then stop. It is
a portfolio piece, not a product with a roadmap to narrate.

**Assets to produce.** The 60-second Loom. A before/after of a grounded finding versus a
plausible-sounding ungrounded one. A screenshot of the disputed-severity flag. The eval table.

**Watch-outs.** Do not imply this is legal advice, and do not overclaim the eval — the
contracts are synthetic and the set is tiny. The entire brand here is not overclaiming; a
post that oversells the numbers undoes more than it wins.

**Next steps.**
- [ ] Post #1: the grounding gate — "it threw away a finding, and that's the point"
- [ ] Post #2: the Loom, with the click-to-source moment as the hook
- [ ] Post #3: the eval table with limitations stated first
- [ ] Optional #4: the 429-vs-credit-exhaustion bug, as a short engineering story

**Status:** _not started_
