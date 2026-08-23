import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Shield, UserPlus } from "lucide-react";
import { useMemo, useState } from "react";
import { ApiError } from "@/api/client";
import {
	createInvitation,
	type Invitation,
	listInvitations,
} from "@/api/invitations";
import { queryKeys } from "@/api/query-keys";
import {
	deactivateUser,
	demoteUser,
	listUsers,
	promoteUser,
	reactivateUser,
	type User,
	type UserAction,
} from "@/api/users";
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Skeleton } from "@/components/ui/Skeleton";

type Tab = "users" | "invitations";

const USER_ACTIONS: Record<UserAction, (userId: string) => Promise<User>> = {
	deactivate: deactivateUser,
	reactivate: reactivateUser,
	promote: promoteUser,
	demote: demoteUser,
};

function errorText(error: unknown): string | null {
	if (error instanceof ApiError) return error.message;
	return error ? "Something went wrong" : null;
}

function StatusBadge({
	label,
	tone,
}: {
	label: string;
	tone: "green" | "red" | "neutral" | "amber";
}) {
	const tones = {
		green:
			"bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
		red: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
		neutral:
			"bg-neutral-100 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-300",
		amber:
			"bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
	} as const;
	return (
		<span
			className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${tones[tone]}`}
		>
			{label}
		</span>
	);
}

function UsersSection() {
	const queryClient = useQueryClient();
	const usersQuery = useQuery({
		queryKey: queryKeys.admin.users(),
		queryFn: listUsers,
	});
	const [actionError, setActionError] = useState<string | null>(null);

	const manageMutation = useMutation({
		mutationFn: ({ userId, action }: { userId: string; action: UserAction }) =>
			USER_ACTIONS[action](userId),
		onSuccess: async () => {
			setActionError(null);
			await queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
			await queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
		},
		onError: (error) =>
			setActionError(errorText(error) ?? "Something went wrong"),
	});

	if (usersQuery.isLoading) {
		return (
			<div className="flex flex-col gap-2 p-4">
				{[0, 1, 2].map((row) => (
					<Skeleton key={row} className="h-10" />
				))}
			</div>
		);
	}

	if (usersQuery.error) {
		return (
			<p role="alert" className="p-4 text-sm text-red-600 dark:text-red-400">
				{errorText(usersQuery.error) ?? "Could not load Users"}
			</p>
		);
	}

	const actionsFor = (user: User) => [
		user.is_admin
			? { label: "Demote", action: "demote" as const }
			: { label: "Promote", action: "promote" as const },
		user.is_active
			? { label: "Deactivate", action: "deactivate" as const }
			: { label: "Reactivate", action: "reactivate" as const },
	];

	return (
		<div>
			{actionError && (
				<p
					role="alert"
					className="mx-4 mt-3 text-sm text-red-600 dark:text-red-400"
				>
					{actionError}
				</p>
			)}
			<table className="w-full text-sm">
				<thead>
					<tr className="border-b border-neutral-200 text-left text-xs uppercase tracking-wider text-neutral-400 dark:border-neutral-800">
						<th className="px-4 py-2 font-semibold">User</th>
						<th className="px-4 py-2 font-semibold">Role</th>
						<th className="px-4 py-2 font-semibold">Status</th>
						<th className="px-4 py-2 text-right font-semibold">Actions</th>
					</tr>
				</thead>
				<tbody>
					{usersQuery.data.map((user) => (
						<tr
							key={user.id}
							className="border-b border-neutral-100 last:border-0 dark:border-neutral-800/60"
						>
							<td className="px-4 py-2">
								<div className="flex items-center gap-2">
									<Avatar
										user={{
											displayName: user.display_name ?? user.email,
											avatarUrl: user.avatar_url,
										}}
									/>
									<div className="min-w-0">
										<div className="truncate font-medium text-neutral-900 dark:text-neutral-100">
											{user.display_name ?? user.email}
										</div>
										<div className="truncate text-xs text-neutral-500">
											{user.email}
										</div>
									</div>
								</div>
							</td>
							<td className="px-4 py-2">
								{user.is_admin ? (
									<StatusBadge label="Admin" tone="amber" />
								) : (
									<StatusBadge label="Member" tone="neutral" />
								)}
							</td>
							<td className="px-4 py-2">
								{user.is_active ? (
									<StatusBadge label="Active" tone="green" />
								) : (
									<StatusBadge label="Deactivated" tone="red" />
								)}
							</td>
							<td className="px-4 py-2">
								<div className="flex justify-end gap-2">
									{actionsFor(user).map(({ label, action }) => (
										<Button
											key={action}
											variant="secondary"
											className="h-7 px-2 text-xs"
											disabled={manageMutation.isPending}
											onClick={() =>
												manageMutation.mutate({
													userId: user.id,
													action,
												})
											}
										>
											{label}
										</Button>
									))}
								</div>
							</td>
						</tr>
					))}
				</tbody>
			</table>
		</div>
	);
}

function InvitationsSection({ usersById }: { usersById: Map<string, User> }) {
	const queryClient = useQueryClient();
	const invitationsQuery = useQuery({
		queryKey: queryKeys.admin.invitations(),
		queryFn: listInvitations,
	});
	const [email, setEmail] = useState("");
	const [newToken, setNewToken] = useState<string | null>(null);
	const [copied, setCopied] = useState(false);
	const [copyFailed, setCopyFailed] = useState(false);
	const [formError, setFormError] = useState<string | null>(null);

	const inviteMutation = useMutation({
		mutationFn: (inviteEmail: string) => createInvitation(inviteEmail),
		onSuccess: (invitation) => {
			setNewToken(invitation.token);
			setCopied(false);
			setCopyFailed(false);
			setEmail("");
			setFormError(null);
			queryClient.invalidateQueries({ queryKey: ["admin", "invitations"] });
		},
		onError: (error) =>
			setFormError(errorText(error) ?? "Could not send the invitation"),
	});

	const copyToken = async () => {
		if (!newToken) return;
		setCopyFailed(false);
		try {
			await navigator.clipboard.writeText(newToken);
			setCopied(true);
		} catch {
			// navigator.clipboard is missing outside secure contexts (plain-HTTP
			// dev over a local IP) — fall back to a hidden textarea + execCommand.
			try {
				const textarea = document.createElement("textarea");
				textarea.value = newToken;
				textarea.setAttribute("readonly", "");
				textarea.style.position = "fixed";
				textarea.style.opacity = "0";
				document.body.appendChild(textarea);
				textarea.select();
				const copiedOk = document.execCommand("copy");
				document.body.removeChild(textarea);
				if (copiedOk) {
					setCopied(true);
					return;
				}
			} catch {
				// execCommand also unavailable — report below
			}
			setCopyFailed(true);
		}
	};

	const statusOf = (invitation: Invitation) => {
		if (invitation.accepted_at)
			return { label: "Accepted", tone: "green" as const };
		if (invitation.expires_at.getTime() < Date.now())
			return { label: "Expired", tone: "red" as const };
		return { label: "Pending", tone: "amber" as const };
	};

	const submit = (event: React.FormEvent) => {
		event.preventDefault();
		const trimmed = email.trim();
		if (!trimmed) return;
		inviteMutation.mutate(trimmed);
	};

	return (
		<div>
			<form onSubmit={submit} className="flex items-end gap-3 p-4">
				<div className="flex-1">
					<Input
						label="Email"
						type="email"
						value={email}
						onChange={setEmail}
						placeholder="teammate@example.com"
					/>
				</div>
				<Button type="submit" disabled={inviteMutation.isPending}>
					<UserPlus size={16} />
					{inviteMutation.isPending ? "Inviting…" : "Invite"}
				</Button>
			</form>
			{formError && (
				<p
					role="alert"
					className="mx-4 mb-2 text-sm text-red-600 dark:text-red-400"
				>
					{formError}
				</p>
			)}
			{newToken && (
				<div className="mx-4 mb-3 rounded-md border border-accent/40 bg-accent/5 p-3">
					<p className="text-xs text-neutral-600 dark:text-neutral-300">
						Share this token with the invitee — it is shown only once.
					</p>
					<div className="mt-2 flex items-center gap-2">
						<code className="flex-1 truncate font-mono text-xs text-neutral-900 dark:text-neutral-100">
							{newToken}
						</code>
						<Button
							variant="secondary"
							className="h-7 px-2 text-xs"
							onClick={copyToken}
						>
							<Copy size={14} />
							{copied ? "Copied" : "Copy"}
						</Button>
					</div>
					{copyFailed && (
						<p className="mt-2 text-xs text-red-600 dark:text-red-400">
							Copy failed — select the token and copy manually.
						</p>
					)}
				</div>
			)}

			{invitationsQuery.isLoading ? (
				<div className="flex flex-col gap-2 p-4">
					{[0, 1].map((row) => (
						<Skeleton key={row} className="h-8" />
					))}
				</div>
			) : invitationsQuery.error ? (
				<p role="alert" className="p-4 text-sm text-red-600 dark:text-red-400">
					{errorText(invitationsQuery.error) ?? "Could not load Invitations"}
				</p>
			) : (
				<table className="w-full text-sm">
					<thead>
						<tr className="border-b border-neutral-200 text-left text-xs uppercase tracking-wider text-neutral-400 dark:border-neutral-800">
							<th className="px-4 py-2 font-semibold">Email</th>
							<th className="px-4 py-2 font-semibold">Invited by</th>
							<th className="px-4 py-2 font-semibold">Status</th>
							<th className="px-4 py-2 font-semibold">Expires</th>
						</tr>
					</thead>
					<tbody>
						{(invitationsQuery.data ?? []).map((invitation) => (
							<tr
								key={invitation.id}
								className="border-b border-neutral-100 last:border-0 dark:border-neutral-800/60"
							>
								<td className="px-4 py-2">{invitation.email}</td>
								<td className="px-4 py-2 text-neutral-500">
									{usersById.get(invitation.invited_by)?.email ?? "—"}
								</td>
								<td className="px-4 py-2">
									<StatusBadge
										label={statusOf(invitation).label}
										tone={statusOf(invitation).tone}
									/>
								</td>
								<td className="px-4 py-2 text-neutral-500">
									{invitation.expires_at.toLocaleDateString()}
								</td>
							</tr>
						))}
					</tbody>
				</table>
			)}
		</div>
	);
}

/**
 * Admin screen (brief §7.2.7): User management (deactivate/reactivate,
 * promote/demote) and Invitations (invite by email, list statuses).
 * Reachable by workspace Admins only (route guard + sidebar).
 */
export function Admin() {
	const [tab, setTab] = useState<Tab>("users");
	const usersQuery = useQuery({
		queryKey: queryKeys.admin.users(),
		queryFn: listUsers,
	});
	const usersById = useMemo(
		() => new Map((usersQuery.data ?? []).map((user) => [user.id, user])),
		[usersQuery.data],
	);

	return (
		<div className="mx-auto w-full max-w-4xl p-6">
			<h1 className="flex items-center gap-2 text-lg font-semibold">
				<Shield size={18} className="text-accent" />
				Admin
			</h1>
			<div
				role="tablist"
				aria-label="Admin sections"
				className="mt-4 flex gap-1 border-b border-neutral-200 dark:border-neutral-800"
			>
				{(["users", "invitations"] as const).map((value) => (
					<button
						key={value}
						type="button"
						id={`tab-${value}`}
						role="tab"
						aria-selected={tab === value}
						aria-controls={`panel-${value}`}
						onClick={() => setTab(value)}
						className={
							"-mb-px border-b-2 px-3 py-1.5 text-sm font-medium focus-visible:outline-accent focus:outline-2 " +
							(tab === value
								? "border-accent text-accent"
								: "border-transparent text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200")
						}
					>
						{value === "users" ? "Users" : "Invitations"}
					</button>
				))}
			</div>
			<div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
				{tab === "users" ? (
					<UsersSection />
				) : (
					<InvitationsSection usersById={usersById} />
				)}
			</div>
		</div>
	);
}
