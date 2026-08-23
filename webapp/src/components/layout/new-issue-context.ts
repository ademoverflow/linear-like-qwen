import { createContext, useContext } from "react";

export interface NewIssueContextValue {
	/** Open the New Issue dialog; `teamId` preselects the Team. */
	open: (teamId?: string) => void;
}

export const NewIssueContext = createContext<NewIssueContextValue | null>(null);

/** Access the global New Issue dialog (opened by the `C` shortcut or a page). */
export function useNewIssue(): NewIssueContextValue {
	const context = useContext(NewIssueContext);
	if (!context) {
		throw new Error(
			"useNewIssue must be used within a NewIssueContext provider",
		);
	}
	return context;
}
