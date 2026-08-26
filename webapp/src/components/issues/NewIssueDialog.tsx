import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ApiError } from "@/api/client";
import { createIssue } from "@/api/issues";
import { queryKeys } from "@/api/query-keys";
import { listTeams } from "@/api/teams";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";

interface NewIssueDialogProps {
	open: boolean;
	/** Team preselected when the dialog was opened from a Team page. */
	defaultTeamId?: string;
	onClose: () => void;
}

/** Create an Issue: title (1–255, trimmed) + Team (brief §3.2). */
export function NewIssueDialog({
	open,
	defaultTeamId,
	onClose,
}: NewIssueDialogProps) {
	const queryClient = useQueryClient();
	const { data: teams } = useQuery({
		queryKey: queryKeys.teams.all(),
		queryFn: listTeams,
	});
	const [title, setTitle] = useState("");
	const [teamId, setTeamId] = useState("");
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		if (open) {
			setTitle("");
			setError(null);
			setTeamId(
				defaultTeamId ?? (teams && teams.length > 0 ? teams[0].id : ""),
			);
		}
	}, [open, defaultTeamId, teams]);

	const createMutation = useMutation({
		mutationFn: (input: { team_id: string; title: string }) =>
			createIssue(input),
		onSuccess: async () => {
			await queryClient.invalidateQueries({ queryKey: ["issues"] });
			onClose();
		},
	});

	const submit = (event: React.FormEvent) => {
		event.preventDefault();
		const trimmed = title.trim();
		if (trimmed.length === 0) {
			setError("Title is required");
			return;
		}
		if (trimmed.length > 255) {
			setError("Title must be 255 characters or fewer");
			return;
		}
		if (!teamId) {
			setError("Pick a Team for the new Issue");
			return;
		}
		setError(null);
		createMutation.mutate({ team_id: teamId, title: trimmed });
	};

	const dialogError =
		error ??
		(createMutation.error instanceof ApiError
			? createMutation.error.message
			: createMutation.error
				? "Could not create the Issue"
				: null);

	return (
		<Dialog open={open} title="New Issue" onClose={onClose}>
			{teams && teams.length === 0 ? (
				<p className="text-sm text-muted">
					You don't belong to a Team yet. Ask a workspace Admin to create one.
				</p>
			) : (
				<form onSubmit={submit} className="flex flex-col gap-3">
					<Input
						label="Title"
						value={title}
						onChange={setTitle}
						error={error ?? undefined}
						placeholder="What needs to be done?"
					/>
					<Select
						label="Team"
						value={teamId}
						onChange={setTeamId}
						options={(teams ?? []).map((team) => ({
							value: team.id,
							label: `${team.key} · ${team.name}`,
						}))}
					/>
					{dialogError && (
						<p role="alert" className="text-sm text-red-600 dark:text-red-400">
							{dialogError}
						</p>
					)}
					<div className="flex justify-end gap-2">
						<Button variant="secondary" onClick={onClose}>
							Cancel
						</Button>
						<Button type="submit" disabled={createMutation.isPending}>
							{createMutation.isPending ? "Creating…" : "Create Issue"}
						</Button>
					</div>
				</form>
			)}
		</Dialog>
	);
}
