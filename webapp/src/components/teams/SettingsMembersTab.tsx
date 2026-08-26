import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { queryKeys } from "@/api/query-keys";
import {
	addTeamMember,
	listTeamMemberCandidates,
	listTeamMembers,
	removeTeamMember,
	type TeamMember,
	updateTeamMemberRole,
} from "@/api/teams";
import { Button } from "@/components/ui/Button";
import { toast } from "@/components/ui/Toast";

const ROLE_OPTIONS = [
	{ value: "owner", label: "Owner" },
	{ value: "member", label: "Member" },
];

const ROLE_SELECT_CLASS =
	"h-8 rounded-md border border-neutral-300 bg-surface px-2 text-sm text-foreground focus:border-accent dark:border-neutral-700";

function useInvalidateTeamCaches(teamId: string) {
	const queryClient = useQueryClient();
	return () => {
		void queryClient.invalidateQueries({
			queryKey: queryKeys.teams.members(teamId),
		});
		// The acting user's own role may have changed (self-demotion).
		void queryClient.invalidateQueries({ queryKey: queryKeys.auth.me() });
	};
}

function MemberRow({ member, teamId }: { member: TeamMember; teamId: string }) {
	const invalidate = useInvalidateTeamCaches(teamId);
	const [confirmRemove, setConfirmRemove] = useState(false);

	const changeRole = useMutation({
		mutationFn: (role: "owner" | "member") =>
			updateTeamMemberRole(teamId, member.id, role),
		onSuccess: invalidate,
		onError: (error) =>
			toast(
				error instanceof Error ? error.message : "Could not change the role",
			),
	});

	const remove = useMutation({
		mutationFn: () => removeTeamMember(teamId, member.id),
		onSuccess: invalidate,
		onError: (error) =>
			toast(
				error instanceof Error ? error.message : "Could not remove the member",
			),
	});

	return (
		<li className="flex items-center gap-2">
			<span className="min-w-0 flex-1 truncate text-sm text-foreground">
				{member.display_name}
			</span>
			<select
				aria-label={`Role for ${member.display_name}`}
				value={member.role}
				onChange={(event) =>
					changeRole.mutate(event.target.value as "owner" | "member")
				}
				className={ROLE_SELECT_CLASS}
			>
				{ROLE_OPTIONS.map((option) => (
					<option key={option.value} value={option.value}>
						{option.label}
					</option>
				))}
			</select>
			<Button
				variant="ghost"
				onClick={() => {
					if (confirmRemove) {
						remove.mutate();
					} else {
						setConfirmRemove(true);
						setTimeout(() => setConfirmRemove(false), 3000);
					}
				}}
			>
				{confirmRemove ? "Confirm?" : "Remove"}
			</Button>
		</li>
	);
}

/**
 * Members tab of the Team settings (ticket 08, brief §5.2): list members
 * with their role, promote/demote, remove (two-step) and add an existing
 * User from the active non-members.
 */
export function SettingsMembersTab({ teamId }: { teamId: string }) {
	const queryClient = useQueryClient();
	const invalidate = useInvalidateTeamCaches(teamId);
	const [pickerOpen, setPickerOpen] = useState(false);

	const membersQuery = useQuery({
		queryKey: queryKeys.teams.members(teamId),
		queryFn: () => listTeamMembers(teamId),
	});
	const candidatesQuery = useQuery({
		queryKey: queryKeys.teams.candidates(teamId),
		queryFn: () => listTeamMemberCandidates(teamId),
		enabled: pickerOpen,
	});

	const add = useMutation({
		mutationFn: (userId: string) => addTeamMember(teamId, userId),
		onSuccess: () => {
			invalidate();
			void queryClient.invalidateQueries({
				queryKey: queryKeys.teams.candidates(teamId),
			});
		},
		onError: (error) =>
			toast(
				error instanceof Error ? error.message : "Could not add the member",
			),
	});

	return (
		<div className="flex flex-col gap-4">
			<ul className="flex flex-col gap-2">
				{membersQuery.data?.map((member) => (
					<MemberRow key={member.id} member={member} teamId={teamId} />
				))}
			</ul>
			<Button
				variant="secondary"
				aria-expanded={pickerOpen}
				onClick={() => setPickerOpen((open) => !open)}
			>
				{pickerOpen ? "Hide candidates" : "Add member"}
			</Button>
			{pickerOpen && (
				<ul
					aria-label="Member candidates"
					className="flex flex-col gap-1 rounded-md border border-line p-1"
				>
					{candidatesQuery.isPending ? (
						<li className="px-2 py-1 text-sm text-faint">Loading…</li>
					) : (candidatesQuery.data ?? []).length === 0 ? (
						<li className="px-2 py-1 text-sm text-faint">
							No other active Users to add.
						</li>
					) : (
						(candidatesQuery.data ?? []).map((candidate) => (
							<li key={candidate.id}>
								<Button
									variant="ghost"
									className="justify-start"
									disabled={add.isPending}
									onClick={() => add.mutate(candidate.id)}
								>
									<span className="truncate">{candidate.display_name}</span>
									<span className="truncate text-xs text-faint">
										{candidate.email}
									</span>
								</Button>
							</li>
						))
					)}
				</ul>
			)}
		</div>
	);
}
