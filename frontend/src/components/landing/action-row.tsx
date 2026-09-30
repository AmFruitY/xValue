const actions = [
  { label: "Explore Players", primary: true },
  { label: "Compare" },
  { label: "Shortlist" },
  { label: "Methodology" },
];

export function ActionRow() {
  return (
    <div className="grid grid-cols-2 gap-2.5 sm:flex sm:flex-wrap">
      {actions.map((action) => (
        <button
          key={action.label}
          type="button"
          disabled
          className={`action-button inline-flex h-11 items-center justify-center gap-2 rounded-full border px-3 text-[0.82rem] font-semibold transition-colors sm:h-12 sm:gap-3 sm:px-5 sm:text-sm ${
            action.primary
              ? "border-accent bg-accent text-[#09110f]"
              : "border-white/12 bg-white/[0.025] text-white/72"
          }`}
        >
          {action.label}
          {action.primary ? <span aria-hidden="true">↗</span> : null}
        </button>
      ))}
    </div>
  );
}
