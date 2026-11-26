"use client";

import { useState, type FocusEvent, type InputHTMLAttributes } from "react";
import { tw } from "@/components/layout/linkwise-theme";

export function AuthField({
  label,
  hint,
  error,
  onFocus,
  onBlur,
  ...inputProps
}: {
  label: string;
  hint?: string;
  error?: string | null;
} & InputHTMLAttributes<HTMLInputElement>) {
  const id = inputProps.id ?? inputProps.name;
  const [focused, setFocused] = useState(false);

  const showHint = Boolean(hint && focused && !error);
  const describedBy = error || showHint ? `${id}-hint` : undefined;

  return (
    <label className="flex flex-col gap-2 text-sm text-[#EDE6DE]" htmlFor={id}>
      {label}
      <input
        id={id}
        className={`${tw.input} ${error ? "border-red-400/60" : ""}`}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        {...inputProps}
        onFocus={(e: FocusEvent<HTMLInputElement>) => {
          setFocused(true);
          onFocus?.(e);
        }}
        onBlur={(e: FocusEvent<HTMLInputElement>) => {
          setFocused(false);
          onBlur?.(e);
        }}
      />
      {error ? (
        <span id={`${id}-hint`} className="text-xs text-red-200">
          {error}
        </span>
      ) : showHint ? (
        <span id={`${id}-hint`} className="text-xs text-[#F0DCC8]">
          {hint}
        </span>
      ) : null}
    </label>
  );
}