export function CairnMark({ className = "" }: { className?: string }) {
  return (
    <svg
      className={className}
      width="30"
      height="32"
      viewBox="0 0 30 32"
      fill="none"
      aria-hidden="true"
    >
      <path d="M14 1h10l3 8H11l3-8Z" fill="currentColor" />
      <path d="M5 12h18l3 8H2l3-8Z" fill="currentColor" />
      <path d="M5 23h20l5 8H0l5-8Z" fill="currentColor" />
    </svg>
  );
}

export function Wordmark() {
  return (
    <span className="wordmark">
      <CairnMark />
      <span>cairn</span>
    </span>
  );
}
