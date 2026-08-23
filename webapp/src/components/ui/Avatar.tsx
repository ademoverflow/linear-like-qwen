interface AvatarUser {
	displayName: string;
	avatarUrl?: string | null;
}

/** User avatar: image when available, initials otherwise; circle when unassigned. */
export function Avatar({
	user,
	size = 20,
}: {
	user: AvatarUser | null;
	size?: number;
}) {
	if (!user) {
		return (
			<div
				className="rounded-full bg-neutral-300 dark:bg-neutral-700"
				style={{ width: size, height: size }}
				role="img"
				aria-label="Unassigned"
			/>
		);
	}
	if (user.avatarUrl) {
		return (
			<img
				src={user.avatarUrl}
				alt={user.displayName}
				className="shrink-0 rounded-full object-cover"
				style={{ width: size, height: size }}
			/>
		);
	}
	const initials = user.displayName
		.trim()
		.split(/\s+/)
		.map((part) => part[0])
		.slice(0, 2)
		.join("")
		.toUpperCase();
	return (
		<div
			className="flex shrink-0 items-center justify-center rounded-full bg-accent font-medium text-white"
			style={{ width: size, height: size, fontSize: size * 0.45 }}
			title={user.displayName}
			role="img"
			aria-label={user.displayName}
		>
			{initials}
		</div>
	);
}
