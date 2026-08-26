import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "@tanstack/react-router";
import { useId, useState } from "react";
import { queryKeys } from "@/api/query-keys";
import {
	archiveTeam,
	listTeams,
	restoreTeam,
	type Team,
	updateTeam,
} from "@/api/teams";
import { LabelManager } from "@/components/teams/LabelManager";
import { SettingsMembersTab } from "@/components/teams/SettingsMembersTab";
import { SettingsWorkflowTab } from "@/components/teams/SettingsWorkflowTab";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Skeleton } from "@/components/ui/Skeleton";
import { toast } from "@/components/ui/Toast";
import { useCurrentUser } from "@/hooks/use-current-user";
import { isOwnerOrAdmin } from "@/lib/permissions";

type Tab = "members" | "labels" | "workflow";

const TABS: { id: Tab; label: string }[] = [
	{ id: "members", label: "Members" },
	{ id: "labels", label: "Labels" },
	{ id: "workflow", label: "Workflow" },
];

const TEXTAREA_CLASS =
	"min-h-24 w-full rounded-md border border-neutral-300 bg-surface px-3 py-2 text-sm text-foreground placeholder:text-faint focus:border-accent dark:border-neutral-700";

/**
 * The Team name/description form (ticket 08, brief §7.2.6) plus the
 * Admin-only two-step Archive. The key is immutable and has no input.
 */
function TeamSection({ team, isAdmin }: { team: Team; isAdmin: boolean }) {
	const queryClient = useQueryClient();
	const descriptionId = useId();
	const [name, setName] = useState(team.name);
	const [description, setDescription] = useState(team.description ?? "");
	const [confirmArchive, setConfirmArchive] = useState(false);

	const dirty =
		name.trim() !== team.name ||
		description.trim() !== (team.description ?? "");

	const save = useMutation({
		mutationFn: () =>
			updateTeam(team.id, {
				name: name.trim(),
				description: description.trim() === "" ? null : description.trim(),
			}),
		onSuccess: () => {
			void queryClient.invalidateQueries({ queryKey: queryKeys.teams.all() });
			void queryClient.invalidateQueries({ queryKey: queryKeys.auth.me() });
		},
		onError: (error) =>
			toast(error instanceof Error ? error.message : "Could not save the Team"),
	});

	const archive = useMutation({
		mutationFn: () => archiveTeam(team.id),
		onSuccess: () => {
			void queryClient.invalidateQueries({ queryKey: queryKeys.teams.all() });
			void queryClient.invalidateQueries({ queryKey: queryKeys.auth.me() });
		},
		onError: (error) =>
			toast(
				error instanceof Error ? error.message : "Could not archive the Team",
			),
	});

	return (
		<section aria-label="Team" className="flex flex-col gap-3">
			<h2 className="text-sm font-semibold text-foreground">Team</h2>
			<form
				className="flex flex-col gap-3"
				onSubmit={(event) => {
					event.preventDefault();
					if (dirty && !save.isPending) save.mutate();
				}}
			>
				<Input label="Name" value={name} onChange={setName} />
				<div className="flex flex-col gap-1.5">
					<label
						className="text-sm font-medium text-foreground"
						htmlFor={descriptionId}
					>
						Description
					</label>
					<textarea
						id={descriptionId}
						value={description}
						onChange={(event) => setDescription(event.target.value)}
						placeholder="What is this Team about?"
						className={TEXTAREA_CLASS}
					/>
				</div>
				<div className="flex items-center gap-2">
					<Button type="submit" disabled={!dirty || save.isPending}>
						{save.isPending ? "Saving…" : "Save"}
					</Button>
					{isAdmin && (
						<Button
							variant="secondary"
							onClick={() => {
								if (confirmArchive) {
									archive.mutate();
								} else {
									setConfirmArchive(true);
									setTimeout(() => setConfirmArchive(false), 3000);
								}
							}}
						>
							{confirmArchive ? "Confirm archive?" : "Archive Team"}
						</Button>
					)}
				</div>
			</form>
		</section>
	);
}

/**
 * Team settings (ticket 08, brief §7.2.6/§6): the Team section
 * (name/description, Admin archive) and the owner/Admin tabs — Members,
 * Labels and the Workflow editor. A non-owner member who reaches the URL
 * sees an "owner access" message; an archived Team shows a banner with
 * the Admin Restore and no tabs.
 */
export function TeamSettings() {
	// `from` matches by routeId; the pathless "app" layout prefixes child ids.
	const { teamKey } = useParams({ from: "/app/teams/$teamKey/settings" });
	const queryClient = useQueryClient();
	const [tab, setTab] = useState<Tab>("members");
	const [confirmRestore, setConfirmRestore] = useState(false);

	const me = useCurrentUser().data;
	const teamsQuery = useQuery({
		queryKey: queryKeys.teams.all(),
		queryFn: listTeams,
	});
	const team = teamsQuery.data?.find((item) => item.key === teamKey);

	const restore = useMutation({
		mutationFn: (teamId: string) => restoreTeam(teamId),
		onSuccess: () => {
			void queryClient.invalidateQueries({ queryKey: queryKeys.teams.all() });
			void queryClient.invalidateQueries({ queryKey: queryKeys.auth.me() });
		},
		onError: (error) =>
			toast(
				error instanceof Error ? error.message : "Could not restore the Team",
			),
	});

	if (teamsQuery.isLoading) {
		return (
			<div className="flex max-w-2xl flex-col gap-2 p-4">
				<Skeleton className="h-16 w-full" />
				<Skeleton className="h-40 w-full" />
			</div>
		);
	}
	if (!team) {
		return (
			<CenteredMessage>
				<h1 className="text-lg font-semibold">Team not found</h1>
				<p className="mt-2 text-sm text-muted">
					No Team with the key {teamKey} is visible to you.
				</p>
			</CenteredMessage>
		);
	}
	if (team.archived_at != null) {
		return (
			<CenteredMessage>
				<h1 className="text-lg font-semibold">This Team is archived</h1>
				<p className="mt-2 text-sm text-muted">
					Its data is kept. A workspace Admin can restore it to make it visible
					again.
				</p>
				{me?.is_admin && (
					<Button
						className="mt-4"
						onClick={() => {
							if (confirmRestore) {
								restore.mutate(team.id);
							} else {
								setConfirmRestore(true);
								setTimeout(() => setConfirmRestore(false), 3000);
							}
						}}
					>
						{confirmRestore ? "Confirm restore?" : "Restore Team"}
					</Button>
				)}
			</CenteredMessage>
		);
	}
	if (!isOwnerOrAdmin(me, team.id)) {
		return (
			<CenteredMessage>
				<h1 className="text-lg font-semibold">Owner access required</h1>
				<p className="mt-2 text-sm text-muted">
					Editing the Team, its members and its Workflow requires owner access.
				</p>
			</CenteredMessage>
		);
	}

	return (
		<div className="flex h-full flex-col">
			<div className="sticky top-0 z-10 border-b border-line bg-surface/90 px-4 py-2 backdrop-blur">
				<nav aria-label="Breadcrumb">
					<span className="text-sm font-semibold">{team.key}</span>
					<span className="mx-1.5 text-faint">›</span>
					<span className="text-sm text-muted">Settings</span>
				</nav>
			</div>

			<div className="flex-1 overflow-y-auto">
				<div className="mx-auto flex w-full max-w-2xl flex-col gap-6 p-4">
					<TeamSection team={team} isAdmin={me?.is_admin === true} />

					<nav aria-label="Settings tabs" className="flex gap-2">
						{TABS.map(({ id, label }) => (
							<Button
								key={id}
								variant="secondary"
								aria-pressed={tab === id}
								className={tab === id ? "border-accent text-accent" : ""}
								onClick={() => setTab(id)}
							>
								{label}
							</Button>
						))}
					</nav>

					{tab === "members" && <SettingsMembersTab teamId={team.id} />}
					{tab === "labels" && <LabelManager teamId={team.id} />}
					{tab === "workflow" && <SettingsWorkflowTab teamId={team.id} />}
				</div>
			</div>
		</div>
	);
}

function CenteredMessage({ children }: { children: React.ReactNode }) {
	return (
		<div className="flex min-h-[50vh] flex-col items-center justify-center p-8 text-center">
			{children}
		</div>
	);
}
