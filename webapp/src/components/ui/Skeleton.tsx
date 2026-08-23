/** Loading placeholder — a calm pulse, never a spinner (brief §7.4). */
export function Skeleton({ className = "" }: { className?: string }) {
	return (
		<div
			aria-hidden
			className={`animate-pulse rounded bg-neutral-200 dark:bg-neutral-800 ${className}`}
		/>
	);
}
