"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getProjects, createProject, createRepo } from "@/lib/api";
import type { Project, Viewport } from "@/lib/types";
import { relativeTime, scorePct } from "@/lib/format";
import { ScoreRing } from "@/components/ScoreRing";
import { PhonePreview } from "@/components/PhonePreview";

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
          <div className="grid grid-cols-2 gap-5">
            {[0, 1].map((i) => (
              <div key={i} className="card h-[260px] shimmer" />
            ))}
          </div>
        ) : projects.length === 0 ? (
          <EmptyState onNew={() => setShowNew(true)} />
        ) : (
          <div className="grid grid-cols-2 gap-5">
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
    <div className="card group flex gap-5 p-6 transition-all duration-200 ease-out">
      <PhonePreview url={project.stagingUrl} />
      <div className="flex min-w-0 flex-1 flex-col justify-between">
        <div>
          <Link
            href={`/projects/${project.id}`}
            className="font-display text-[20px] text-primary no-underline hover:underline"
          >
            {project.name}
          </Link>
          <p className="mt-1 text-[13px] text-secondary">
            {project.personaCount} persona{project.personaCount !== 1 ? "s" : ""}
          </p>
        </div>
        <div className="flex items-center justify-between">
          <div className="flex gap-2">
            {project.repoUrl && (
              <a
                href={project.repoUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 rounded-lg bg-field px-2.5 py-1.5 text-[12px] text-secondary no-underline transition-colors hover:text-primary"
              >
                <svg className="h-3.5 w-3.5" fill="currentColor" viewBox="0 0 16 16">
                  <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
                </svg>
                Repo
              </a>
            )}
            {project.stagingUrl && (
              <a
                href={project.stagingUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 rounded-lg bg-field px-2.5 py-1.5 text-[12px] text-secondary no-underline transition-colors hover:text-primary"
              >
                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
                Live
              </a>
            )}
          </div>
          <div className="flex items-center gap-3">
            {project.latestScore != null && (
              <ScoreRing value={project.latestScore} size={48} />
            )}
          </div>
        </div>
        <div className="mt-2 text-[12px] text-tertiary">
          {relativeTime(project.lastRunAt)}
        </div>
      </div>
    </div>
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
  const [repoUrl, setRepoUrl] = useState("");
  const [viewport, setViewport] = useState<Viewport>("desktop");
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    const p = await createProject({
      name: name.trim(),
      description: description.trim() || undefined,
      repoUrl: repoUrl.trim() || undefined,
      stagingUrl: stagingUrl.trim() || undefined,
    });
    if (repoName.trim() && stagingUrl.trim()) {
      await createRepo(p.id, {
        name: repoName.trim(),
        stagingUrl: stagingUrl.trim(),
        repoUrl: repoUrl.trim() || undefined,
        viewport,
      });
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
            <Field label="Repository URL">
              <input
                type="url"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                className="input"
                placeholder="https://github.com/org/repo"
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
