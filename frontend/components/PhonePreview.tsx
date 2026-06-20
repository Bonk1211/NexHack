export function PhonePreview({ url }: { url?: string }) {
  if (!url) {
    return (
      <div className="phone-frame flex items-center justify-center bg-field">
        <span className="text-[12px] text-tertiary">No preview</span>
      </div>
    );
  }

  return (
    <div className="phone-frame">
      <iframe
        src={url}
        title="Site preview"
        className="h-full w-full border-0"
        sandbox="allow-scripts allow-same-origin"
      />
    </div>
  );
}
