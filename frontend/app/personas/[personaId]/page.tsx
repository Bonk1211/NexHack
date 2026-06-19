"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  getPersona,
  updatePersona,
  createPersona,
  generateFigurine,
  pollFigurine,
} from "@/lib/api";
import type { Persona, FigurineStatus } from "@/lib/types";
import { behaviorSentence } from "@/lib/format";

const AGE_BANDS = ["18–24", "25–34", "35–44", "45–54", "55–64", "65+"];
const DISABILITY_OPTIONS = [
  "low vision",
  "screen reader",
  "colour vision",
  "keyboard only",
  "motor",
  "dyslexia",
  "hearing",
  "cognitive",
];

export default function PersonaDetailPage() {
  const params = useParams();
  const router = useRouter();
  const personaId = params.personaId as string;
  const isNew = personaId === "new";

  const [persona, setPersona] = useState<Persona | null>(null);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);

  const [name, setName] = useState("");
  const [label, setLabel] = useState("");
  const [ageBand, setAgeBand] = useState("25–34");
  const [language, setLanguage] = useState("English");
  const [disabilities, setDisabilities] = useState<string[]>([]);
  const [techSavviness, setTechSavviness] = useState(0.5);
  const [patience, setPatience] = useState(0.5);
  const [dwellMultiplier, setDwellMultiplier] = useState(1);
  const [hesitationProb, setHesitationProb] = useState(0.3);
  const [giveupThresholdS, setGiveupThresholdS] = useState(60);

  const [figurineStatus, setFigurineStatus] = useState<FigurineStatus>("none");
  const [figurineUrl, setFigurineUrl] = useState<string | undefined>();

  useEffect(() => {
    if (isNew) {
      setLoading(false);
      return;
    }
    getPersona(personaId).then((p) => {
      setPersona(p);
      setName(p.name);
      setLabel(p.label);
      setAgeBand(p.ageBand);
      setLanguage(p.language);
      setDisabilities(p.disabilities);
      setTechSavviness(p.techSavviness);
      setPatience(p.patience);
      setDwellMultiplier(p.behaviorProfile.dwellMultiplier);
      setHesitationProb(p.behaviorProfile.hesitationProb);
      setGiveupThresholdS(p.behaviorProfile.giveupThresholdS);
      setFigurineStatus(p.figurineStatus);
      setFigurineUrl(p.figurineUrl);
      setLoading(false);
    });
  }, [personaId, isNew]);

  const pollUntilReady = useCallback(async (id: string) => {
    for (let i = 0; i < 10; i++) {
      const res = await pollFigurine(id);
      if (res.status === "ready") {
        setFigurineStatus("ready");
        setFigurineUrl(res.url);
        return;
      }
      if (res.status === "failed") {
        setFigurineStatus("failed");
        return;
      }
    }
    setFigurineStatus("failed");
  }, []);

  async function handleGenerate() {
    if (!persona) return;
    setFigurineStatus("generating");
    await generateFigurine(persona.id);
    pollUntilReady(persona.id);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    const data = {
      name: name.trim(),
      label: label.trim(),
      ageBand,
      language,
      disabilities,
      techSavviness,
      patience,
      behaviorProfile: {
        dwellMultiplier,
        hesitationProb,
        readingSpeedWpm: 200,
        giveupThresholdS,
        retryLimit: 3,
      },
    };
    if (isNew) {
      const created = await createPersona(data);
      router.push(`/personas/${created.id}`);
    } else {
      const updated = await updatePersona(personaId, data);
      setPersona(updated);
    }
    setSaving(false);
  }

  function toggleDisability(d: string) {
    setDisabilities((prev) =>
      prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d],
    );
  }

  const previewSentence = behaviorSentence({
    name: name || "This persona",
    techSavviness,
    patience,
    behaviorProfile: { dwellMultiplier, hesitationProb, giveupThresholdS },
  });

  if (loading) {
    return (
      <div className="px-10 py-10">
        <div className="h-8 w-48 shimmer rounded-lg" />
        <div className="mt-6 grid grid-cols-2 gap-8">
          <div className="card h-[500px] shimmer" />
          <div className="card h-[400px] shimmer" />
        </div>
      </div>
    );
  }

  return (
    <div className="px-10 py-10">
      <div className="mb-6 flex items-center gap-2 text-[13px] text-secondary">
        <Link href="/personas" className="text-brand no-underline hover:underline">
          Personas
        </Link>
        <span>/</span>
        <span className="text-primary">{name || "New persona"}</span>
      </div>

      <form onSubmit={handleSave}>
        <div className="grid grid-cols-2 gap-8">
          <div className="space-y-5">
            <h1 className="font-display text-[28px] text-primary">
              {isNew ? "New persona" : name}
            </h1>

            <Field label="Name">
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="input"
                required
              />
            </Field>
            <Field label="Label">
              <input
                type="text"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                className="input"
                placeholder="OKU — visual (low-vision)"
              />
            </Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Age band">
                <select
                  value={ageBand}
                  onChange={(e) => setAgeBand(e.target.value)}
                  className="input"
                >
                  {AGE_BANDS.map((b) => (
                    <option key={b} value={b}>{b}</option>
                  ))}
                </select>
              </Field>
              <Field label="Language">
                <input
                  type="text"
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  className="input"
                />
              </Field>
            </div>

            <Field label="Disabilities">
              <div className="flex flex-wrap gap-2">
                {DISABILITY_OPTIONS.map((d) => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => toggleDisability(d)}
                    className={`rounded-full px-3 py-1 text-[12px] font-medium transition-colors ${
                      disabilities.includes(d)
                        ? "bg-brand text-white"
                        : "bg-field text-secondary hover:bg-hairline"
                    }`}
                  >
                    {d}
                  </button>
                ))}
              </div>
            </Field>

            <div className="border-t border-hairline pt-5">
              <div className="section-label mb-4">Behavior profile</div>
              <SliderField
                label="Tech savviness"
                value={techSavviness}
                onChange={setTechSavviness}
                min={0}
                max={1}
                step={0.05}
              />
              <SliderField
                label="Patience"
                value={patience}
                onChange={setPatience}
                min={0}
                max={1}
                step={0.05}
              />
              <SliderField
                label="Dwell multiplier"
                value={dwellMultiplier}
                onChange={setDwellMultiplier}
                min={0.5}
                max={3}
                step={0.1}
              />
              <SliderField
                label="Hesitation probability"
                value={hesitationProb}
                onChange={setHesitationProb}
                min={0}
                max={1}
                step={0.05}
              />
              <SliderField
                label="Give-up threshold (s)"
                value={giveupThresholdS}
                onChange={setGiveupThresholdS}
                min={10}
                max={120}
                step={5}
              />
            </div>

            <div className="rounded-xl bg-field p-4 text-[13px] text-secondary italic">
              {previewSentence}
            </div>

            <button
              type="submit"
              disabled={saving || !name.trim()}
              className="w-full rounded-xl bg-brand py-3 text-[14px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {saving ? "Saving..." : isNew ? "Create persona" : "Save changes"}
            </button>
          </div>

          <div>
            <div className="card p-6">
              <div className="section-label mb-4">Figurine</div>
              <div className="flex flex-col items-center">
                <div className="h-32 w-32 overflow-hidden rounded-full bg-field">
                  {figurineStatus === "ready" && figurineUrl ? (
                    <img
                      src={figurineUrl}
                      alt={name}
                      className="h-32 w-32 rounded-full object-cover"
                    />
                  ) : figurineStatus === "generating" ? (
                    <div className="h-32 w-32 shimmer rounded-full" />
                  ) : (
                    <div className="flex h-32 w-32 items-center justify-center text-tertiary">
                      <span className="text-[40px]">?</span>
                    </div>
                  )}
                </div>
                <div className="mt-4">
                  {figurineStatus === "failed" ? (
                    <div className="text-center">
                      <p className="text-[13px] text-blocked">Generation failed</p>
                      <button
                        type="button"
                        onClick={handleGenerate}
                        className="mt-2 rounded-lg bg-brand px-4 py-2 text-[13px] font-medium text-white"
                      >
                        Retry
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={handleGenerate}
                      disabled={!persona || figurineStatus === "generating"}
                      className="rounded-lg bg-brand px-4 py-2 text-[13px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
                    >
                      {figurineStatus === "generating"
                        ? "Generating..."
                        : figurineStatus === "ready"
                          ? "Regenerate"
                          : "Generate figurine"}
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </form>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1.5 block text-[12px] font-semibold uppercase tracking-[0.06em] text-tertiary">
        {label}
      </label>
      {children}
    </div>
  );
}

function SliderField({
  label,
  value,
  onChange,
  min,
  max,
  step,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step: number;
}) {
  return (
    <div className="mb-4">
      <div className="mb-1 flex items-center justify-between">
        <span className="text-[13px] text-secondary">{label}</span>
        <span className="text-[13px] font-medium tabular-nums text-primary">
          {value.toFixed(step < 1 ? 2 : 0)}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full accent-brand"
      />
    </div>
  );
}
