import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Monitor, Moon, Sun } from "lucide-react";
import type { Theme } from "@/api/auth";
import { queryKeys, updateMe } from "@/api/auth";
import { toast } from "@/components/ui/Toast";

const OPTIONS: { value: Theme; label: string; icon: typeof Monitor }[] = [
	{ value: "system", label: "System", icon: Monitor },
	{ value: "light", label: "Light", icon: Sun },
	{ value: "dark", label: "Dark", icon: Moon },
];

function labelOf(preference: Theme): string {
	return (
		OPTIONS.find((option) => option.value === preference)?.label ?? "System"
	);
}

/**
 * Theme preference switcher (ticket 10): System / Light / Dark. The choice
 * is persisted per User via PATCH /auth/me (brief §7.4) and applied by the
 * useThemePreference owner (AppShell) from the updated me. Collapsed
 * sidebar: one button that cycles through the three.
 */
export function ThemeSwitcher({
	preference,
	onChange,
	collapsed = false,
}: {
	preference: Theme;
	onChange: (preference: Theme) => void;
	collapsed?: boolean;
}) {
	const queryClient = useQueryClient();
	const mutation = useMutation({
		mutationFn: (theme: Theme) => updateMe({ theme }),
		onSuccess: (me) => {
			queryClient.setQueryData(queryKeys.auth.me(), me);
			onChange(me.theme);
		},
		onError: (error: unknown) =>
			toast(
				error instanceof Error ? error.message : "Could not change the theme",
			),
	});

	const select = (theme: Theme) => mutation.mutate(theme);

	if (collapsed) {
		const index = OPTIONS.findIndex((option) => option.value === preference);
		const next = OPTIONS[(index + 1) % OPTIONS.length];
		return (
			<button
				type="button"
				aria-label={`Theme: ${labelOf(preference)}`}
				title={`Theme: ${labelOf(preference)} (switches to ${next.label})`}
				onClick={() => select(next.value)}
				disabled={mutation.isPending}
				className="flex w-full items-center justify-center rounded-md px-2 py-1.5 text-sm text-muted hover:bg-surface-subtle hover:text-foreground disabled:opacity-50"
			>
				<next.icon size={16} aria-hidden />
			</button>
		);
	}

	return (
		// biome-ignore lint/a11y/useSemanticElements: fieldset would imply form semantics; this groups the three theme toggles
		<div
			role="group"
			aria-label="Theme"
			className="flex flex-1 items-center gap-0.5"
		>
			{OPTIONS.map((option) => (
				<button
					key={option.value}
					type="button"
					aria-label={`Theme: ${option.label}`}
					aria-pressed={preference === option.value}
					title={option.label}
					onClick={() => select(option.value)}
					disabled={mutation.isPending}
					className={
						"flex-1 rounded-md px-2 py-1.5 text-sm disabled:opacity-50 " +
						(preference === option.value
							? "bg-surface-subtle text-foreground"
							: "text-muted hover:bg-surface-subtle hover:text-foreground")
					}
				>
					<option.icon size={16} aria-hidden />
					<span className="sr-only">{option.label}</span>
				</button>
			))}
		</div>
	);
}
