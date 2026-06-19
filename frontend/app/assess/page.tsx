import AssessmentRunner from "@/components/AssessmentRunner";

export default function AssessPage() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="font-display text-[28px] text-primary">Run an inclusion assessment</h1>
      <p className="mt-1 mb-6 text-[14px] text-secondary">
        Loads the target in a mobile viewport, drives the flow per persona via the accessibility
        tree (vision-LLM fallback), screenshots every step, across ≥3 personas.
      </p>
      <AssessmentRunner />
    </main>
  );
}
