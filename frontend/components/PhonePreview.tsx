export function PhonePreview({ url, compact }: { url?: string; compact?: boolean }) {
  const frame = compact ? "phone-frame-sm" : "phone-frame";

  if (!url) {
    return (
      <div className={`${frame} flex items-center justify-center`}>
        <span className="text-[12px] text-tertiary">No preview</span>
      </div>
    );
  }

  return (
    <div className={frame}>
      <iframe
        src={url}
        title="Site preview"
        sandbox="allow-scripts allow-same-origin"
      />
    </div>
  );
}
