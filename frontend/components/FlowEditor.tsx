"use client";

import { useState, useRef } from "react";
import type { FlowStep } from "@/lib/types";

const ACTIONS: FlowStep["action"][] = ["fill", "click", "view"];

function emptyStep(): FlowStep {
  return { key: "", action: "click", role: "button", name: "", value: "", critical: false };
}

export function FlowEditor({
  steps: initial,
  onSave,
  onClose,
}: {
  steps: FlowStep[];
  onSave: (steps: FlowStep[]) => Promise<void>;
  onClose: () => void;
}) {
  const [steps, setSteps] = useState<FlowStep[]>(initial.length > 0 ? initial : [emptyStep()]);
  const [saving, setSaving] = useState(false);
  const dragIdx = useRef<number | null>(null);
  const dragOverIdx = useRef<number | null>(null);

  function update(idx: number, patch: Partial<FlowStep>) {
    setSteps((prev) => prev.map((s, i) => (i === idx ? { ...s, ...patch } : s)));
  }

  function remove(idx: number) {
    setSteps((prev) => prev.filter((_, i) => i !== idx));
  }

  function add() {
    setSteps((prev) => [...prev, emptyStep()]);
  }

  function onDragStart(idx: number) {
    dragIdx.current = idx;
  }

  function onDragOver(e: React.DragEvent, idx: number) {
    e.preventDefault();
    dragOverIdx.current = idx;
  }

  function onDrop() {
    const from = dragIdx.current;
    const to = dragOverIdx.current;
    if (from === null || to === null || from === to) return;
    setSteps((prev) => {
      const next = [...prev];
      const [moved] = next.splice(from, 1);
      next.splice(to, 0, moved);
      return next;
    });
    dragIdx.current = null;
    dragOverIdx.current = null;
  }

  async function handleSave() {
    setSaving(true);
    const cleaned = steps.filter((s) => s.key.trim());
    await onSave(cleaned);
    setSaving(false);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm" onClick={onClose}>
      <div className="w-[560px] max-h-[80vh] overflow-y-auto rounded-[20px] bg-card p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h3 className="font-display text-[20px] text-primary">Configure flow steps</h3>
          <button type="button" onClick={onClose} className="text-[14px] text-secondary hover:text-primary">
            Close
          </button>
        </div>
        <p className="mt-1 text-[13px] text-secondary">
          Define the steps the agent will execute. Drag to reorder.
        </p>

        <div className="mt-5 space-y-3">
          {steps.map((step, idx) => (
            <div
              key={idx}
              draggable
              onDragStart={() => onDragStart(idx)}
              onDragOver={(e) => onDragOver(e, idx)}
              onDrop={onDrop}
              className="card flex items-start gap-3 p-4 cursor-grab active:cursor-grabbing"
            >
              <div className="mt-1 flex flex-col items-center gap-0.5 text-tertiary">
                <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M7 2a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM13 2a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM7 8a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM13 8a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM7 14a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM13 14a2 2 0 1 0 0 4 2 2 0 0 0 0-4z" />
                </svg>
              </div>

              <div className="flex-1 space-y-2">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[11px] font-semibold uppercase tracking-[0.06em] text-tertiary">Key</label>
                    <input
                      className="input mt-1"
                      value={step.key}
                      onChange={(e) => update(idx, { key: e.target.value })}
                      placeholder="login"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold uppercase tracking-[0.06em] text-tertiary">Action</label>
                    <select
                      className="input mt-1"
                      value={step.action}
                      onChange={(e) => update(idx, { action: e.target.value as FlowStep["action"] })}
                    >
                      {ACTIONS.map((a) => (
                        <option key={a} value={a}>{a}</option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[11px] font-semibold uppercase tracking-[0.06em] text-tertiary">Role</label>
                    <input
                      className="input mt-1"
                      value={step.role}
                      onChange={(e) => update(idx, { role: e.target.value })}
                      placeholder="textbox"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold uppercase tracking-[0.06em] text-tertiary">Name</label>
                    <input
                      className="input mt-1"
                      value={step.name}
                      onChange={(e) => update(idx, { name: e.target.value })}
                      placeholder="Email"
                    />
                  </div>
                </div>
                {step.action === "fill" && (
                  <div>
                    <label className="text-[11px] font-semibold uppercase tracking-[0.06em] text-tertiary">Value</label>
                    <input
                      className="input mt-1"
                      value={step.value}
                      onChange={(e) => update(idx, { value: e.target.value })}
                      placeholder="test@example.com"
                    />
                  </div>
                )}
                <label className="flex items-center gap-2 text-[12px] text-secondary">
                  <input
                    type="checkbox"
                    checked={step.critical}
                    onChange={(e) => update(idx, { critical: e.target.checked })}
                    className="h-3.5 w-3.5 rounded"
                  />
                  Critical step
                </label>
              </div>

              <button
                type="button"
                onClick={() => remove(idx)}
                className="mt-1 text-[12px] text-secondary hover:text-blocked"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          ))}
        </div>

        <div className="mt-4 flex items-center justify-between">
          <button
            type="button"
            onClick={add}
            className="rounded-lg bg-field px-4 py-2 text-[13px] font-medium text-primary transition-colors hover:bg-field/80"
          >
            + Add step
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="rounded-xl bg-brand px-5 py-2.5 text-[14px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save flow"}
          </button>
        </div>
      </div>
    </div>
  );
}
