import { Outlet, useNavigate } from "@tanstack/react-router";
import { Menu } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError } from "@/api/client";
import { NewIssueDialog } from "@/components/issues/NewIssueDialog";
import { Toaster } from "@/components/ui/Toast";
import { env } from "@/env";
import { useCurrentUser } from "@/hooks/use-current-user";
import { useMediaQuery } from "@/hooks/use-media-query";
import { useShortcut } from "@/hooks/use-shortcut";
import { useThemePreference } from "@/hooks/use-theme";
import {
	NewIssueContext,
	type NewIssueContextValue,
} from "./new-issue-context";
import { SearchOverlay } from "./SearchOverlay";
import { ShortcutCheatsheet } from "./ShortcutCheatsheet";
import { Sidebar } from "./Sidebar";
import { SidebarDrawer } from "./SidebarDrawer";

/**
 * Authenticated layout (brief §7.1, §7.3, §7.4): sidebar + main area, the
 * global shortcuts (`C` new Issue, `/` and Cmd/Ctrl+K search, `?`
 * cheat-sheet) and the New Issue dialog. Below 768px the sidebar becomes
 * an off-canvas drawer (ticket 10). The theme preference is owned here:
 * it starts from the stored mirror (applied pre-paint in index.html) and
 * syncs from `me.theme` once the profile loads (ticket 10, ADR 0014).
 */
export function AppShell() {
	const { data: me, error } = useCurrentUser();
	const navigate = useNavigate();
	const isDesktop = useMediaQuery("(min-width: 768px)");
	const { preference, setPreference } = useThemePreference();
	const [newIssue, setNewIssue] = useState<{
		open: boolean;
		defaultTeamId?: string;
	}>({ open: false });
	const [searchOpen, setSearchOpen] = useState(false);
	const [cheatsheetOpen, setCheatsheetOpen] = useState(false);
	const [sidebarOpen, setSidebarOpen] = useState(false);

	useEffect(() => {
		// The profile's theme preference is authoritative.
		if (me && me.theme !== preference) setPreference(me.theme);
	}, [me, preference, setPreference]);

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
	const closeSidebar = useCallback(() => setSidebarOpen(false), []);
	const openSearchFromDrawer = useCallback(() => {
		setSidebarOpen(false);
		setSearchOpen(true);
	}, []);

	const contextValue = useMemo<NewIssueContextValue>(
		() => ({ open: openNewIssue }),
		[openNewIssue],
	);

	if (!me) {
		return <div className="h-screen bg-canvas" />;
	}

	return (
		<NewIssueContext.Provider value={contextValue}>
			<div className="flex h-screen bg-canvas text-foreground">
				{isDesktop && (
					<Sidebar
						onOpenSearch={openSearch}
						themePreference={preference}
						onThemeChange={setPreference}
					/>
				)}
				<div className="flex min-w-0 flex-1 flex-col">
					{!isDesktop && (
						<header className="flex h-12 shrink-0 items-center gap-2 border-b border-line bg-surface px-3">
							<button
								type="button"
								aria-label="Open sidebar"
								className="rounded-md p-1.5 text-faint hover:bg-surface-subtle hover:text-foreground"
								onClick={() => setSidebarOpen(true)}
							>
								<Menu size={18} aria-hidden />
							</button>
							<span className="truncate text-sm font-semibold">
								{env.VITE_APP_TITLE ?? "Linear Like Qwen"}
							</span>
						</header>
					)}
					<main className="min-h-0 flex-1 overflow-y-auto">
						<Outlet />
					</main>
				</div>
				{!isDesktop && sidebarOpen && (
					<SidebarDrawer open onClose={closeSidebar}>
						<Sidebar
							forceExpanded
							onOpenSearch={openSearchFromDrawer}
							onNavigate={closeSidebar}
							themePreference={preference}
							onThemeChange={setPreference}
						/>
					</SidebarDrawer>
				)}
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
			</div>
		</NewIssueContext.Provider>
	);
}
