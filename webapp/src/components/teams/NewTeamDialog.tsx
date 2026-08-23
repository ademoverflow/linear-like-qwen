import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ApiError } from "@/api/client";
import { createTeam } from "@/api/teams";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Input";

const TEAM_KEY_PATTERN = /^[A-Z]{2,5}$/;

/** Admin creates a Team (brief §6); the creating Admin becomes owner. */
export function NewTeamDialog({
	open,
	onClose,
}: {
	open: boolean;
	onClose: () => void;
}) {
	const queryClient = useQueryClient();
	const [name, setName] = useState("");
	const [key, setKey] = useState("");
	const [description, setDescription] = useState("");
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		if (open) {
			setName("");
			setKey("");
			setDescription("");
			setError(null);
		}
	}, [open]);

	const createMutation = useMutation({
		mutationFn: (input: { name: string; key: string; description?: string }) =>
			createTeam(input),
		onSuccess: async () => {
			await queryClient.invalidateQueries({ queryKey: ["teams"] });
			await queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
			onClose();
		},
	});

	const submit = (event: React.FormEvent) => {
		event.preventDefault();
		const trimmedName = name.trim();
		const trimmedKey = key.trim().toUpperCase();
		if (trimmedName.length === 0) {
			setError("Name is required");
			return;
		}
		if (!TEAM_KEY_PATTERN.test(trimmedKey)) {
			setError("Key must be 2–5 uppercase letters (A–Z)");
			return;
		}
		setError(null);
		createMutation.mutate({
			name: trimmedName,
			key: trimmedKey,
			description: description.trim() || undefined,
		});
	};

	const dialogError =
		error ??
		(createMutation.error instanceof ApiError
			? createMutation.error.message
			: createMutation.error
				? "Could not create the Team"
				: null);

	return (
		<Dialog open={open} title="New Team" onClose={onClose}>
			<form onSubmit={submit} className="flex flex-col gap-3">
				<Input
					label="Name"
					value={name}
					onChange={setName}
					placeholder="Engineering"
				/>
				<Input
					label="Key"
					value={key}
					onChange={(value) => setKey(value.toUpperCase())}
					error={error ?? undefined}
					placeholder="ENG"
				/>
				<Input
					label="Description (optional)"
					value={description}
					onChange={setDescription}
					placeholder="What this Team works on"
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
						{createMutation.isPending ? "Creating…" : "Create Team"}
					</Button>
				</div>
			</form>
		</Dialog>
	);
}
