import type { ReactNode } from "react";
import { useId } from "react";

interface InputProps {
	label: ReactNode;
	value: string;
	onChange: (value: string) => void;
	error?: string;
	type?: "text" | "email" | "password";
	placeholder?: string;
	disabled?: boolean;
}

/** Labeled text input with an optional inline error (aria-describedby). */
export function Input({
	label,
	value,
	onChange,
	error,
	type = "text",
	placeholder,
	disabled,
}: InputProps) {
	const id = useId();
	const errorId = error ? `${id}-error` : undefined;
	return (
		<div className="flex flex-col gap-1.5">
			<label htmlFor={id} className="text-sm font-medium text-foreground">
				{label}
			</label>
			<input
				id={id}
				type={type}
				value={value}
				onChange={(event) => onChange(event.target.value)}
				placeholder={placeholder}
				disabled={disabled}
				aria-invalid={error ? true : undefined}
				aria-describedby={errorId}
				className="h-9 rounded-md border border-neutral-300 bg-surface px-3 text-sm text-foreground placeholder:text-faint focus:border-accent dark:border-neutral-700"
			/>
			{error && (
				<p id={errorId} className="text-xs text-red-600 dark:text-red-400">
					{error}
				</p>
			)}
		</div>
	);
}
