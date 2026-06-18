// Persona wall (§14) — the demo surface. SCAFFOLD.
// Centerpiece per §14: one panel per persona + empathy replay + the friction
// matrix (the hero diff: same screen passes control, blocks a protected group).
// The wall is presentation polish (~20 marks) — build the engine + evidence first (§21, §24).

const PERSONAS = [
  "elderly_low_literacy",
  "oku_visual",
  "oku_motor",
  "oku_hearing",
  "low_literacy",
  "non_native",
  "low_end_device",
  "control",
];

export default function Home() {
  return (
    <main style={{ padding: 32, maxWidth: 1100, margin: "0 auto" }}>
      <h1 style={{ marginBottom: 4 }}>InclusionScope</h1>
      <p style={{ opacity: 0.7, marginTop: 0 }}>
        Persona wall — inclusion assurance as audit evidence. (scaffold)
      </p>

      {/* TODO(§14): per-persona live/replay panels; empathy-replay clips
          (low-vision contrast/blur filter, colorblind filter, enlarged-tap
          overlay, slowed interaction) rendered over the per-step screenshots. */}
      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
          gap: 12,
          marginTop: 24,
        }}
      >
        {PERSONAS.map((p) => (
          <div
            key={p}
            style={{ border: "1px solid #232838", borderRadius: 10, padding: 16 }}
          >
            <div style={{ fontWeight: 600 }}>{p}</div>
            <div style={{ opacity: 0.6, fontSize: 13, marginTop: 6 }}>idle</div>
          </div>
        ))}
      </section>

      {/* TODO(FR-3.3, §14): persona × step friction matrix — the hero artifact. */}
    </main>
  );
}
