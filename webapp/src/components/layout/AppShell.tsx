import { Outlet, useNavigate } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError } from "@/api/client";
import { NewIssueDialog } from "@/components/issues/NewIssueDialog";
import { Toaster } from "@/components/ui/Toast";
import { useCurrentUser } from "@/hooks/use-current-user";
import { useShortcut } from "@/hooks/use-shortcut";
import {
	NewIssueContext,
	type NewIssueContextValue,
} from "./new-issue-context";
import { SearchOverlay } from "./SearchOverlay";
import { ShortcutCheatsheet } from "./ShortcutCheatsheet";
import { Sidebar } from "./Sidebar";

/**
 * Authenticated layout: collapsible sidebar + main area, the global
 * shortcuts (`C` new Issue, `/` and Cmd/Ctrl+K search, `?` cheat-sheet)
 * and the New Issue dialog (brief §7.1, §7.2.8, §7.3).
 */
export function AppShell() {
	const { data: me, error } = useCurrentUser();
	const navigate = useNavigate();
	const [newIssue, setNewIssue] = useState<{
		open: boolean;
		defaultTeamId?: string;
	}>({ open: false });
	const [searchOpen, setSearchOpen] = useState(false);
	const [cheatsheetOpen, setCheatsheetOpen] = useState(false);

	useEffect(() => {
		// Mid-session token expiry: fall back to login.
		if (error instanceof ApiError && error.status === 401) {
			navigate({ to: "/login", replace: true });
		}
	}, [error, navigate]);

	const openNewIssue = useCallback(
		(teamId?: string) => setNewIssue({ open: true, defaultTeamId: teamId }),
		[],
	);
	useShortcut("c", () => openNewIssue());
	const toggleSearch = useCallback(() => setSearchOpen((value) => !value), []);
	useShortcut("/", toggleSearch);
	useShortcut("k", toggleSearch, { modifier: true });
	useShortcut("?", () => setCheatsheetOpen(true));

	const openSearch = useCallback(() => setSearchOpen(true), []);
	const closeSearch = useCallback(() => setSearchOpen(false), []);

	const contextValue = useMemo<NewIssueContextValue>(
		() => ({ open: openNewIssue }),
		[openNewIssue],
	);

	if (!me) {
		return <div className="h-screen bg-neutral-50 dark:bg-neutral-950" />;
	}

	return (
		<NewIssueContext.Provider value={contextValue}>
			<div className="flex h-screen bg-neutral-50 text-neutral-900 dark:bg-neutral-950 dark:text-neutral-100">
				<Sidebar onOpenSearch={openSearch} />
				<main className="flex-1 overflow-y-auto">
					<Outlet />
				</main>
			</div>
			<NewIssueDialog
				open={newIssue.open}
				defaultTeamId={newIssue.defaultTeamId}
				onClose={() => setNewIssue({ open: false })}
			/>
			<SearchOverlay open={searchOpen} onClose={closeSearch} />
			<ShortcutCheatsheet
				open={cheatsheetOpen}
				onClose={() => setCheatsheetOpen(false)}
			/>
			<Toaster />
		</NewIssueContext.Provider>
	);
}
