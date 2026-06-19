"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getProjects, createProject, createRepo } from "@/lib/api";
import type { Project, Viewport } from "@/lib/types";
import { relativeTime, scorePct } from "@/lib/format";
import { ScoreRing } from "@/components/ScoreRing";

export default function Home() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [showNew, setShowNew] = useState(false);

  useEffect(() => {
    getProjects().then((p) => {
      setProjects(p);
      setLoading(false);
    });
  }, []);

  return (
    <div>
      <div className="bg-anchor px-10 pt-16 pb-14">
        <div className="rise">
          <div className="text-[11px] font-semibold uppercase tracking-[0.1em] text-on-dark-dim">
            InclusionScope
          </div>
          <h1 className="mt-3 font-display text-[40px] leading-tight text-on-dark">
            Audit every user. Before they leave.
          </h1>
          <p className="mt-2 max-w-lg text-[15px] text-on-dark-dim">
            Persona-driven accessibility audits that show who gets blocked — and exactly why.
          </p>
          <button
            type="button"
            onClick={() => setShowNew(true)}
            className="mt-6 rounded-xl bg-brand px-5 py-2.5 text-[14px] font-medium text-white transition-opacity hover:opacity-90"
          >
            New project
          </button>
        </div>
      </div>

      <div className="px-10 py-10">
        {loading ? (
          <div className="grid grid-cols-3 gap-5">
            {[0, 1, 2].map((i) => (
              <div key={i} className="card h-[140px] shimmer" />
            ))}
          </div>
        ) : projects.length === 0 ? (
          <EmptyState onNew={() => setShowNew(true)} />
        ) : (
          <div className="grid grid-cols-3 gap-5">
            {projects.map((p, i) => (
              <div key={p.id} className="rise" style={{ animationDelay: `${i * 30}ms` }}>
                <ProjectCard project={p} />
              </div>
            ))}
          </div>
        )}
      </div>

      {showNew && (
        <NewProjectSlideOver
          onClose={() => setShowNew(false)}
          onCreated={(p) => {
            setProjects((prev) => [...prev, p]);
            setShowNew(false);
          }}
        />
      )}
    </div>
  );
}

function ProjectCard({ project }: { project: Project }) {
  return (
    <Link
      href={`/projects/${project.id}`}
      className="card group block p-6 no-underline transition-all duration-200 ease-out hover:-translate-y-0.5"
    >
      <div className="flex items-start justify-between">
        <div className="min-w-0 flex-1">
          <h3 className="truncate font-display text-[20px] text-primary">{project.name}</h3>
          <p className="mt-1 text-[13px] text-secondary">
            {project.personaCount} persona{project.personaCount !== 1 ? "s" : ""}
          </p>
        </div>
        {project.latestScore != null && (
          <ScoreRing value={project.latestScore} size={56} />
        )}
      </div>
      <div className="mt-4 text-[12px] text-tertiary">
        {relativeTime(project.lastRunAt)}
      </div>
    </Link>
  );
}

function EmptyState({ onNew }: { onNew: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-24">
      <div className="card p-10 text-center">
        <div className="font-display text-[24px] text-primary">No projects yet</div>
        <p className="mt-2 text-[14px] text-secondary">
          Create your first project to start auditing your onboarding flows.
        </p>
        <button
          type="button"
          onClick={onNew}
          className="mt-5 rounded-xl bg-brand px-5 py-2.5 text-[14px] font-medium text-white transition-opacity hover:opacity-90"
        >
          Create project
        </button>
      </div>
    </div>
  );
}

function NewProjectSlideOver({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (p: Project) => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [repoName, setRepoName] = useState("");
  const [stagingUrl, setStagingUrl] = useState("");
  const [viewport, setViewport] = useState<Viewport>("desktop");
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    const p = await createProject({ name: name.trim(), description: description.trim() || undefined });
    if (repoName.trim() && stagingUrl.trim()) {
      await createRepo(p.id, { name: repoName.trim(), stagingUrl: stagingUrl.trim(), viewport });
    }
    onCreated(p);
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30 backdrop-blur-sm" onClick={onClose}>
      <div
        className="h-full w-[420px] overflow-y-auto bg-card p-8 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="font-display text-[24px] text-primary">New project</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-[14px] text-secondary hover:text-primary"
          >
            Close
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-8 space-y-5">
          <Field label="Project name">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="input"
              placeholder="MyDigital ID Onboarding"
              required
            />
          </Field>
          <Field label="Description">
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="input min-h-[80px]"
              placeholder="National e-ID sign-up flow"
            />
          </Field>

          <div className="border-t border-hairline pt-5">
            <div className="section-label mb-4">First repo</div>
            <Field label="Repo name">
              <input
                type="text"
                value={repoName}
                onChange={(e) => setRepoName(e.target.value)}
                className="input"
                placeholder="mydigital-web (staging)"
              />
            </Field>
            <Field label="Staging URL">
              <input
                type="url"
                value={stagingUrl}
                onChange={(e) => setStagingUrl(e.target.value)}
                className="input"
                placeholder="https://staging.example.com"
              />
            </Field>
            <Field label="Viewport">
              <select
                value={viewport}
                onChange={(e) => setViewport(e.target.value as Viewport)}
                className="input"
              >
                <option value="desktop">Desktop</option>
                <option value="tablet">Tablet</option>
                <option value="mobile">Mobile</option>
              </select>
            </Field>
          </div>

          <button
            type="submit"
            disabled={saving || !name.trim()}
            className="w-full rounded-xl bg-brand py-3 text-[14px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {saving ? "Creating..." : "Create project"}
          </button>
        </form>
      </div>
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
