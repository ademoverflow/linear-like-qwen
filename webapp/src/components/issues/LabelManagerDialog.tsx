import { LabelManager } from "@/components/teams/LabelManager";
import { Dialog } from "@/components/ui/Dialog";

/**
 * Owner-managed Label dialog (ticket 05, brief §5.2/§9), reached from the
 * Issues list toolbar. The content is shared with the Team settings'
 * Labels tab (ticket 08) via `LabelManager`.
 */
export function LabelManagerDialog({
	teamId,
	onClose,
}: {
	teamId: string;
	onClose: () => void;
}) {
	return (
		<Dialog open title="Labels" onClose={onClose}>
			<LabelManager teamId={teamId} />
		</Dialog>
	);
}
