"use client";

import { useId } from "react";
import type { AmountInput } from "@/lib/predictions/scenarios";

/** Amount in millions of euros. Validation lives in parseMillions; this only shows its message. */
export function AmountField({ label, help, value, parsed, onChange }: { label: string; help: string; value: string; parsed: AmountInput; onChange: (value: string) => void }) {
  const id = useId(), helpId = `${id}-help`, errorId = `${id}-error`;
  const invalid = parsed.status === "invalid";
  return <div className="xv-amount">
    <label htmlFor={id}>{label}</label>
    <div className="xv-amount-field">
      <input id={id} type="text" inputMode="decimal" autoComplete="off" value={value} aria-invalid={invalid} aria-describedby={invalid ? `${helpId} ${errorId}` : helpId} onChange={(event) => onChange(event.target.value)} />
      <span aria-hidden="true">M€</span>
    </div>
    <small id={helpId}>{help}</small>
    {invalid && <small id={errorId} className="xv-amount-error" role="alert">{parsed.message}</small>}
  </div>;
}
