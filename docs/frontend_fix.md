Design overhaul brief — InclusionScope dashboard
Overall principle: this should feel like a precision instrument, not a status dashboard. Restraint over decoration. When in doubt, remove color and reduce weight.
Color system, replace the current palette entirely:

Surfaces: page background #f5f5f7, cards pure white #ffffff. (You have this, keep it.)
Text: primary #1d1d1f, secondary #6e6e73, tertiary #8e8e93. Three greys, no more.
Kill the saturated status fills. New semantic colors, used as accents only (text, dots, thin bars, never large fills): success #1d8a4e (desaturated forest, not #22c55e), warning #b25e00 (amber-brown, not bright orange), critical #c8362f (brick, not #ef4444).
Exactly one brand accent for interactive/primary elements: pick a single blue like #0066cc and use it only for links and the primary CTA. Not for data.

Typography, introduce severe hierarchy:

Font: Inter (or SF Pro Display/Text if licensed), -apple-system fallback.
Hero title ("DemoBank — onboarding"): 32px, weight 600, letter-spacing -0.02em, color #1d1d1f.
Section headers ("Persona wall", "Friction matrix"): do NOT make them big and bold. Make them small and quiet, 13px, weight 600, letter-spacing 0.06em, UPPERCASE, color #8e8e93. This inversion (small quiet section labels, big content) is the single most "Apple" move you can make.
The "INCLUSIONSCOPE" eyebrow: keep it small uppercase tracked, but make it #8e8e93 not blue, unless it's a clickable logo.
Body/meta text: 14px, weight 400, #6e6e73.

The hero card:

Remove the card border entirely. Let it sit on the #f5f5f7 background as pure white with a single very soft shadow: 0 1px 3px rgba(0,0,0,0.04), 0 8px 24px rgba(0,0,0,0.04). Soft, large, barely-there.
Increase internal padding to 40px.
The "71 / SCORE" ring: keep it, but make the ring track #e8e8ed, the progress stroke a single color mapped to score (here amber #b25e00), stroke width thin (6–8px, not chunky). Number 40px weight 600, "SCORE" label 11px uppercase tracked #8e8e93.
The sentence "Silently blocks oku visual, elderly low literacy" — keep the emphasis but make the highlighted terms #c8362f weight 500, not bold red. Subtle.

Persona wall cards, the biggest fix:

Remove the per-card ring gauges entirely. They're noise. Replace with a single small status dot (8px circle) in the top-right: green #1d8a4e, amber #b25e00, or brick #c8362f.
Card: white, no border, the same soft shadow as hero but lighter (0 1px 2px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.03)). Radius 16px. Padding 20px.
Persona name: 17px weight 600 #1d1d1f. Sub-label ("OKU — visual"): 13px #8e8e93.
Status line at bottom: instead of red "Blocked · OTP verify", use a small dot + text: critical dot + "Blocked at OTP verify" in 13px #6e6e73 (let the dot carry the color, keep the text grey). For friction: amber dot + "P2 friction".
This is where your figurines go. Once figurines exist, the persona card leads with the figurine portrait (circular, 48px, top-left), name beside it, status dot top-right. That alone will lift this from generic to distinctive.
On hover: lift shadow slightly + translate up 2px, 200ms ease-out. Nothing more.

Friction matrix, convert from pills to a restrained heatmap:

Kill the solid-color pills completely. This is critical.
Each cell: the time value as the primary element (15px, weight 500, #1d1d1f), sitting on a very subtle tinted background that encodes severity: fast = #f0f7f2 (barely-green), slow = #fbf3ec (barely-amber), blocked/fail = #faeceb (barely-red) with the text in the matching desaturated semantic color. The tint is ~8% opacity, a whisper.
Blocked cells ("—"): show a small × or "blocked" in #c8362f on the faint red tint, not a grey dash that looks like missing data.
Cell borders: none. Separate rows with hairline 1px #f0f0f2 dividers only.
Row header (persona name): 14px weight 500 #1d1d1f. Column headers: 12px uppercase tracked #8e8e93.
Right-align the time values, tabular-nums font feature so digits align.

Spacing & layout:

Section vertical rhythm: 64px between major sections (hero → persona wall → matrix), not the current ~32px. More air.
Max content width 1120px, centered.
Persona wall grid gap: 16px.

Motion:

Cards and rows fade+translate-up 8px on mount, staggered 30ms each, 300ms ease-out. Subtle.
Score ring animates from 0 to value once on load, 800ms ease-out.
No other animation.

Remove entirely:

All per-card ring gauges (replaced by dots).
All solid-color background fills on data elements.
All default card borders (replaced by soft shadow).
The redundant triple-encoding of status, dot carries color, text stays grey.


Two QC checks to hand the dev as acceptance criteria

The squint test: blur your eyes at the screen. You should see a calm white-and-grey layout with a few small colored dots and one amber ring. If you see blocks of saturated green/red, it's not done.
The color-count test: no more than one saturated accent visible per viewport. Everything else is greyscale or barely-tinted.