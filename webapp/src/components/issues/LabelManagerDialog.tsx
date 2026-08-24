import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { queryKeys } from "@/api/query-keys";
import {
	createTeamLabel,
	deleteTeamLabel,
	listTeamLabels,
	updateTeamLabel,
} from "@/api/teams";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { toast } from "@/components/ui/Toast";

const DEFAULT_COLOR = "#f2c94c";

function LabelRow({
	label,
	teamId,
}: {
	label: { id: string; name: string; color: string };
	teamId: string;
}) {
	const queryClient = useQueryClient();
	const [name, setName] = useState(label.name);
	const [color, setColor] = useState(label.color);
	const [confirmDelete, setConfirmDelete] = useState(false);

	const update = useMutation({
		mutationFn: (input: { name?: string; color?: string }) =>
			updateTeamLabel(teamId, label.id, input),
		onSuccess: () => {
			void queryClient.invalidateQueries({
				queryKey: queryKeys.teams.labels(teamId),
			});
			// Issues embed their Labels (name/color): keep those caches fresh.
			void queryClient.invalidateQueries({ queryKey: ["issues"] });
		},
		onError: (error) =>
			toast(
				error instanceof Error ? error.message : "Could not update the Label",
			),
	});

	const remove = useMutation({
		mutationFn: () => deleteTeamLabel(teamId, label.id),
		onSuccess: () => {
			void queryClient.invalidateQueries({
				queryKey: queryKeys.teams.labels(teamId),
			});
			void queryClient.invalidateQueries({ queryKey: ["issues"] });
		},
		onError: (error) =>
			toast(
				error instanceof Error ? error.message : "Could not delete the Label",
			),
	});

	const commitName = () => {
		const trimmed = name.trim();
		if (trimmed.length > 0 && trimmed !== label.name) {
			update.mutate({ name: trimmed });
		} else {
			setName(label.name);
		}
	};

	return (
		<li className="flex items-center gap-2">
			<input
				type="color"
				aria-label={`Colour for ${label.name}`}
				value={color}
				onChange={(event) => setColor(event.target.value)}
				onBlur={() => {
					if (color !== label.color) update.mutate({ color });
				}}
				className="h-7 w-7 shrink-0 cursor-pointer rounded border border-neutral-300 bg-white p-0.5 dark:border-neutral-700 dark:bg-neutral-900"
			/>
			<input
				type="text"
				aria-label={`Name for ${label.name}`}
				value={name}
				maxLength={50}
				onChange={(event) => setName(event.target.value)}
				onBlur={commitName}
				onKeyDown={(event) => {
					if (event.key === "Enter") event.currentTarget.blur();
				}}
				className="min-w-0 flex-1 rounded-md border border-neutral-300 bg-white px-2 py-1 text-sm text-neutral-900 focus:border-accent focus:outline-none dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-100"
			/>
			<Button
				variant="ghost"
				onClick={() => {
					if (confirmDelete) {
						remove.mutate();
					} else {
						setConfirmDelete(true);
						setTimeout(() => setConfirmDelete(false), 3000);
					}
				}}
			>
				{confirmDelete ? "Confirm?" : "Delete"}
			</Button>
		</li>
	);
}

/**
 * Owner-managed Label dialog (ticket 05, brief §5.2/§9): create, rename,
 * recolor and delete a Team's Labels. Team Settings (ticket 08) is not
 * built yet, so this dialog is the management surface for now; it is
 * reached from the Issues list toolbar.
 */
export function LabelManagerDialog({
	teamId,
	onClose,
}: {
	teamId: string;
	onClose: () => void;
}) {
	const queryClient = useQueryClient();
	const [name, setName] = useState("");
	const [color, setColor] = useState(DEFAULT_COLOR);

	const labelsQuery = useQuery({
		queryKey: queryKeys.teams.labels(teamId),
		queryFn: () => listTeamLabels(teamId),
	});

	const create = useMutation({
		mutationFn: () => createTeamLabel(teamId, { name, color }),
		onSuccess: () => {
			setName("");
			void queryClient.invalidateQueries({
				queryKey: queryKeys.teams.labels(teamId),
			});
			void queryClient.invalidateQueries({ queryKey: ["issues"] });
		},
		onError: (error) =>
			toast(
				error instanceof Error ? error.message : "Could not create the Label",
			),
	});

	return (
		<Dialog open title="Labels" onClose={onClose}>
			<ul className="flex flex-col gap-2">
				{labelsQuery.data?.map((label) => (
					<LabelRow key={label.id} label={label} teamId={teamId} />
				))}
			</ul>
			<form
				className="mt-4 flex items-center gap-2"
				onSubmit={(event) => {
					event.preventDefault();
					if (name.trim().length > 0) create.mutate();
				}}
			>
				<input
					type="color"
					aria-label="New Label colour"
					value={color}
					onChange={(event) => setColor(event.target.value)}
					className="h-9 w-9 shrink-0 cursor-pointer rounded-md border border-neutral-300 bg-white p-1 dark:border-neutral-700 dark:bg-neutral-900"
				/>
				<input
					type="text"
					aria-label="New Label name"
					value={name}
					maxLength={50}
					placeholder="Label name"
					onChange={(event) => setName(event.target.value)}
					className="min-w-0 flex-1 rounded-md border border-neutral-300 bg-white px-2 text-sm text-neutral-900 focus:border-accent focus:outline-none dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-100"
				/>
				<Button type="submit" disabled={name.trim().length === 0}>
					Add
				</Button>
			</form>
		</Dialog>
	);
}
