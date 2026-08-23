import { useId } from "react";

interface SelectOption {
	value: string;
	label: string;
}

interface SelectProps {
	label: string;
	value: string;
	onChange: (value: string) => void;
	options: SelectOption[];
}

/** Native select with a visible label (keyboard-friendly by default). */
export function Select({ label, value, onChange, options }: SelectProps) {
	const id = useId();
	return (
		<div className="flex flex-col gap-1.5">
			<label
				htmlFor={id}
				className="text-sm font-medium text-neutral-700 dark:text-neutral-300"
			>
				{label}
			</label>
			<select
				id={id}
				value={value}
				onChange={(event) => onChange(event.target.value)}
				className="h-9 rounded-md border border-neutral-300 bg-white px-2 text-sm text-neutral-900 focus:border-accent focus:outline-none dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-100"
			>
				{options.map((option) => (
					<option key={option.value} value={option.value}>
						{option.label}
					</option>
				))}
			</select>
		</div>
	);
}
