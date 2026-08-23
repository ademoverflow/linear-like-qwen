import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { queryKeys } from "@/api/query-keys";
import { listTeams } from "@/api/teams";
import { NewTeamDialog } from "@/components/teams/NewTeamDialog";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { useCurrentUser } from "@/hooks/use-current-user";

/**
 * Landing state when the user belongs to no Team: Admins can create one,
 * everyone else is told to ask a workspace Admin (brief §6).
 */
export function Home() {
	const { data: me } = useCurrentUser();
	const teamsQuery = useQuery({
		queryKey: queryKeys.teams.all(),
		queryFn: listTeams,
	});
	const [newTeamOpen, setNewTeamOpen] = useState(false);

	if (teamsQuery.isLoading) {
		return (
			<div className="flex justify-center p-8">
				<Skeleton className="h-16 w-64" />
			</div>
		);
	}

	return (
		<div className="flex min-h-full items-center justify-center p-8">
			<div className="w-full max-w-md text-center">
				<h1 className="text-lg font-semibold">No Teams yet</h1>
				{me?.is_admin ? (
					<>
						<p className="mt-2 text-sm text-neutral-500">
							Create the first Team for this Workspace. It comes with the
							default Workflow, and you become its owner.
						</p>
						<div className="mt-4 flex justify-center">
							<Button onClick={() => setNewTeamOpen(true)}>New Team</Button>
						</div>
					</>
				) : (
					<p className="mt-2 text-sm text-neutral-500">
						Ask a workspace Admin to create a Team and add you to it.
					</p>
				)}
			</div>
			<NewTeamDialog open={newTeamOpen} onClose={() => setNewTeamOpen(false)} />
		</div>
	);
}
