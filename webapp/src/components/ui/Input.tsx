import { useId } from "react";

interface InputProps {
	label: string;
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
			<label
				htmlFor={id}
				className="text-sm font-medium text-neutral-700 dark:text-neutral-300"
			>
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
				className="h-9 rounded-md border border-neutral-300 bg-white px-3 text-sm text-neutral-900 placeholder:text-neutral-400 focus:border-accent focus:outline-none dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-100"
			/>
			{error && (
				<p id={errorId} className="text-xs text-red-600 dark:text-red-400">
					{error}
				</p>
			)}
		</div>
	);
}
