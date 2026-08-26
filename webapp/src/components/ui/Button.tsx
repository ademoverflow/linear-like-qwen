import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost";

const VARIANT_CLASSES: Record<Variant, string> = {
	primary: "bg-accent text-white hover:bg-accent/90 disabled:bg-accent/50",
	secondary:
		"border border-neutral-300 bg-surface text-foreground hover:bg-surface-subtle dark:border-neutral-700",
	ghost: "text-muted hover:bg-surface-subtle hover:text-foreground",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
	variant?: Variant;
}

export function Button({
	variant = "primary",
	className = "",
	type = "button",
	...rest
}: ButtonProps) {
	return (
		<button
			type={type}
			className={
				"inline-flex h-8 items-center justify-center gap-1.5 rounded-md px-3 text-sm font-medium transition-colors focus-visible:outline-accent focus:outline-2 focus:outline-offset-1 disabled:cursor-not-allowed disabled:opacity-60 " +
				VARIANT_CLASSES[variant] +
				" " +
				className
			}
			{...rest}
		/>
	);
}
