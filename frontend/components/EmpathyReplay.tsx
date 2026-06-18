"use client";

// THE CENTERPIECE (§14). Render the screen THROUGH a persona's lens via CSS
// filters the judge can toggle. A button disappearing under a low-vision filter
// communicates the exclusion in one second — visible, not asserted.
//
// No backend image dependency: we render a styled mock of the DemoBank OTP screen
// (the planted-flaw fixture) as a DOM "screenshot" and apply the lens over it.
import { useState } from "react";

type LensId = "none" | "low_vision" | "colorblind" | "tap_target" | "slowed";

interface Lens {
  id: LensId;
  label: string;
  hint: string;
  // CSS filter applied to the rendered screen
  filter?: string;
}

const LENSES: Lens[] = [
  { id: "none", label: "Actual", hint: "What the design team sees" },
  {
    id: "low_vision",
    label: "Low vision",
    hint: "Blur + reduced contrast — the unlabeled control fades out",
    filter: "blur(2.2px) contrast(0.55) brightness(1.05)",
  },
  {
    id: "colorblind",
    label: "Colorblind",
    hint: "Deuteranopia approximation — color-only cues collapse",
    filter: "grayscale(0.55) sepia(0.4) hue-rotate(-30deg) saturate(1.4)",
  },
  {
    id: "tap_target",
    label: "Tap targets",
    hint: "44px minimum overlay — undersized targets flagged",
  },
  {
    id: "slowed",
    label: "Slowed interaction",
    hint: "Motor/elderly pacing — dwell stretches past the give-up threshold",
  },
];

// A styled mock of the flawed DemoBank OTP screen. The "Verify" control is an
// unlabeled icon-only button (WCAG 4.1.2) using a tiny, low-contrast hit area —
// exactly the planted flaw the personas trip on.
function ScreenMock({ lens }: { lens: LensId }) {
  const showTapOverlay = lens === "tap_target";
  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        maxWidth: 360,
        margin: "0 auto",
        background: "#f4f6fb",
        color: "#0f172a",
        borderRadius: 14,
        padding: "26px 22px",
        boxShadow: "0 8px 30px rgba(0,0,0,0.45)",
        fontFamily: "system-ui, sans-serif",
      }}
    >
      <div style={{ fontSize: 13, fontWeight: 700, color: "#1d4ed8", letterSpacing: 0.5 }}>DemoBank</div>
      <h3 style={{ margin: "14px 0 4px", fontSize: 20, color: "#0f172a" }}>Enter OTP</h3>
      <p style={{ margin: 0, fontSize: 13, color: "#64748b" }}>
        We sent a 6-digit code to •••• 4821
      </p>

      <div style={{ display: "flex", gap: 8, margin: "20px 0" }}>
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <div
            key={i}
            style={{
              flex: 1,
              height: 44,
              borderRadius: 8,
              border: "1px solid #cbd5e1",
              background: "#fff",
            }}
          />
        ))}
      </div>

      {/* The planted flaw: an icon-only "verify" control with no accessible name,
          tiny hit area, and low-contrast styling. This is what fades / disappears
          under the low-vision lens. */}
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <div style={{ position: "relative", display: "inline-block" }}>
          <button
            // intentionally no aria-label / text — mirrors the WCAG 4.1.2 fail
            style={{
              width: 30,
              height: 30,
              borderRadius: 6,
              border: "none",
              // low-contrast pale-on-pale: vanishes under reduced contrast
              background: "#dfe6f2",
              color: "#aebbd2",
              fontSize: 15,
              cursor: "pointer",
            }}
          >
            ➜
          </button>
          {showTapOverlay && (
            <div
              // 44px minimum target overlay, centered on the 30px control
              style={{
                position: "absolute",
                top: "50%",
                left: "50%",
                width: 44,
                height: 44,
                transform: "translate(-50%, -50%)",
                border: "2px dashed #dc2626",
                borderRadius: 8,
                pointerEvents: "none",
              }}
            >
              <span
                style={{
                  position: "absolute",
                  top: -18,
                  right: 0,
                  fontSize: 10,
                  fontWeight: 700,
                  color: "#dc2626",
                  whiteSpace: "nowrap",
                }}
              >
                30px &lt; 44px min
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function EmpathyReplay() {
  const [lens, setLens] = useState<LensId>("none");
  const active = LENSES.find((l) => l.id === lens)!;
  const slowed = lens === "slowed";

  return (
    <div>
      {/* lens toggles — one per lens */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 8 }}>
        {LENSES.map((l) => {
          const on = l.id === lens;
          return (
            <button
              key={l.id}
              onClick={() => setLens(l.id)}
              aria-pressed={on}
              style={{
                cursor: "pointer",
                fontSize: 13,
                fontWeight: 600,
                padding: "7px 13px",
                borderRadius: 999,
                border: `1px solid ${on ? "#2563eb" : "#2a3142"}`,
                background: on ? "#1d4ed8" : "#161b27",
                color: on ? "#fff" : "#94a3b8",
                transition: "all 0.15s",
              }}
            >
              {l.label}
            </button>
          );
        })}
      </div>

      <div style={{ fontSize: 13, color: "#94a3b8", marginBottom: 14, minHeight: 18 }}>{active.hint}</div>

      <div
        style={{
          position: "relative",
          background: "#0a0d14",
          borderRadius: 14,
          padding: "32px 16px",
          border: "1px solid #1c2231",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            filter: active.filter,
            transition: "filter 0.35s ease",
          }}
        >
          <ScreenMock lens={lens} />
        </div>

        {/* slowed-interaction indicator: a dwell timer overlay communicating the
            stretched pacing for motor/elderly personas. */}
        {slowed && (
          <div
            style={{
              position: "absolute",
              top: 12,
              left: 12,
              display: "flex",
              alignItems: "center",
              gap: 8,
              fontSize: 12,
              fontWeight: 600,
              color: "#fde68a",
              background: "rgba(113,63,18,0.85)",
              padding: "5px 10px",
              borderRadius: 8,
              border: "1px solid #a16207",
            }}
          >
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: "#facc15",
                animation: "isPulse 1.1s ease-in-out infinite",
              }}
            />
            dwell 4.0s · approaching give-up threshold
          </div>
        )}
      </div>

      <p style={{ fontSize: 12, color: "#64748b", marginTop: 10 }}>
        Lens applied over the captured OTP step. Toggle a lens to see the same screen the way that
        persona experiences it.
      </p>
    </div>
  );
}
