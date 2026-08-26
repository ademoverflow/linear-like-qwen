import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useRouter } from "@tanstack/react-router";
import {
	LogOut,
	PanelLeftClose,
	PanelLeftOpen,
	Plus,
	Search,
	Shield,
	User,
} from "lucide-react";
import { useState } from "react";
import { logout, queryKeys, type Theme } from "@/api/auth";
import { listTeams } from "@/api/teams";
import { NewTeamDialog } from "@/components/teams/NewTeamDialog";
import { env } from "@/env";
import { useCurrentUser } from "@/hooks/use-current-user";
import { isOwnerOrAdmin } from "@/lib/permissions";
import { ThemeSwitcher } from "./ThemeSwitcher";

const STORAGE_KEY = "sidebar-collapsed";

function readStoredCollapsed(): boolean {
	try {
		return localStorage.getItem(STORAGE_KEY) === "1";
	} catch {
		return false;
	}
}

/**
 * Collapsible left sidebar (brief §7.1): workspace name, the search
 * trigger, My Issues, the Teams section, the theme switcher and logout.
 * Teams link to their Issues list. In the narrow-screen drawer
 * (`forceExpanded`) the collapse toggle is hidden and `onNavigate` closes
 * the drawer after navigation (ticket 10).
 */
export function Sidebar({
	onOpenSearch,
	forceExpanded = false,
	onNavigate,
	themePreference,
	onThemeChange,
}: {
	onOpenSearch: () => void;
	forceExpanded?: boolean;
	onNavigate?: () => void;
	themePreference: Theme;
	onThemeChange: (preference: Theme) => void;
}) {
	const [collapsed, setCollapsed] = useState(
		forceExpanded ? false : readStoredCollapsed(),
	);
	const queryClient = useQueryClient();
	const { data: me } = useCurrentUser();
	const [newTeamOpen, setNewTeamOpen] = useState(false);
	const { data: teams } = useQuery({
		queryKey: queryKeys.teams.all(),
		queryFn: listTeams,
	});
	const { navigate } = useRouter();

	const logoutMutation = useMutation({
		mutationFn: logout,
		onSettled: () => {
			queryClient.clear();
			navigate({ to: "/login", replace: true });
		},
	});

	const toggle = () => {
		const next = !collapsed;
		setCollapsed(next);
		try {
			localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
		} catch {
			// private mode etc. — collapsing still works, just not persisted
		}
	};

	return (
		<div
			className={
				"flex h-full shrink-0 flex-col border-r border-line bg-surface transition-[width] " +
				(collapsed ? "w-14" : "w-60")
			}
		>
			<div
				className={
					"flex h-12 items-center border-b border-line " +
					(collapsed ? "justify-center" : "justify-between px-3")
				}
			>
				<span
					className={
						"truncate text-sm font-semibold text-foreground " +
						(collapsed ? "sr-only" : "")
					}
				>
					{env.VITE_APP_TITLE ?? "Linear Like Qwen"}
				</span>
				{!forceExpanded && (
					<button
						type="button"
						onClick={toggle}
						aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
						className="rounded p-1.5 text-faint hover:bg-surface-subtle hover:text-foreground"
					>
						{collapsed ? (
							<PanelLeftOpen size={16} />
						) : (
							<PanelLeftClose size={16} />
						)}
					</button>
				)}
			</div>

			<nav className="flex-1 overflow-y-auto p-2" aria-label="Primary">
				<ul className="flex flex-col gap-0.5">
					<li>
						<button
							type="button"
							onClick={() => {
								onOpenSearch();
								onNavigate?.();
							}}
							title="Search"
							className={
								"flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-foreground hover:bg-surface-subtle " +
								(collapsed ? "justify-center" : "")
							}
						>
							<Search size={16} className="shrink-0" />
							{!collapsed && (
								<>
									<span className="flex-1 truncate text-left">Search</span>
									<kbd className="shrink-0 rounded border border-neutral-300 px-1.5 py-0.5 font-mono text-[10px] text-faint dark:border-neutral-700">
										/
									</kbd>
								</>
							)}
						</button>
					</li>
					<li>
						<Link
							to="/my-issues"
							title="My Issues"
							onClick={onNavigate}
							className={
								"flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-foreground hover:bg-surface-subtle " +
								(collapsed ? "justify-center" : "")
							}
						>
							<User size={16} className="shrink-0" />
							{!collapsed && <span className="truncate">My Issues</span>}
						</Link>
					</li>
				</ul>

				{!collapsed && (
					<div className="mb-1 px-2 text-[11px] font-semibold uppercase tracking-wider text-faint">
						Teams
					</div>
				)}
				<ul className="flex flex-col gap-0.5">
					{(teams ?? []).map((team) => (
						<li key={team.id}>
							<Link
								to="/teams/$teamKey/issues"
								params={{ teamKey: team.key }}
								title={team.name}
								onClick={onNavigate}
								className={
									"flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-foreground hover:bg-surface-subtle " +
									(collapsed ? "justify-center" : "")
								}
							>
								<span
									className={
										"shrink-0 font-mono text-xs text-muted " +
										(collapsed ? "" : "w-10")
									}
								>
									{team.key}
								</span>
								{!collapsed && (
									<>
										<span className="truncate">{team.name}</span>
										{team.archived_at != null && (
											<span className="ml-1 shrink-0 rounded-full bg-surface-subtle px-1.5 py-0.5 text-[10px] font-medium text-muted">
												Archived
											</span>
										)}
									</>
								)}
							</Link>
							{!collapsed && (
								<div className="ml-7 mt-0.5 flex flex-col gap-0.5 border-l border-line pl-2">
									<Link
										to="/teams/$teamKey/board"
										params={{ teamKey: team.key }}
										onClick={onNavigate}
										className="rounded px-2 py-1 text-xs text-muted hover:bg-surface-subtle"
									>
										Board
									</Link>
									{isOwnerOrAdmin(me, team.id) && (
										<Link
											to="/teams/$teamKey/settings"
											params={{ teamKey: team.key }}
											onClick={onNavigate}
											className="rounded px-2 py-1 text-xs text-muted hover:bg-surface-subtle"
										>
											Settings
										</Link>
									)}
								</div>
							)}
						</li>
					))}
				</ul>
			</nav>

			<div className="border-t border-line p-2">
				<div
					className={
						"mb-1.5 flex items-center gap-2" +
						(collapsed ? " justify-center" : "")
					}
				>
					{!collapsed && (
						<span className="shrink-0 text-[11px] font-semibold uppercase tracking-wider text-faint">
							Theme
						</span>
					)}
					<ThemeSwitcher
						preference={themePreference}
						onChange={onThemeChange}
						collapsed={collapsed}
					/>
				</div>
				{me?.is_admin && (
					<Link
						to="/admin"
						title="Admin"
						onClick={onNavigate}
						className={
							"flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-muted hover:bg-surface-subtle " +
							(collapsed ? "justify-center" : "")
						}
					>
						<Shield size={16} className="shrink-0" />
						{!collapsed && <span>Admin</span>}
					</Link>
				)}
				{me?.is_admin && (
					<button
						type="button"
						onClick={() => setNewTeamOpen(true)}
						className={
							"flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-muted hover:bg-surface-subtle " +
							(collapsed ? "justify-center" : "")
						}
						title="New Team"
					>
						<Plus size={16} className="shrink-0" />
						{!collapsed && <span>New Team</span>}
					</button>
				)}
				<button
					type="button"
					onClick={() => logoutMutation.mutate()}
					disabled={logoutMutation.isPending}
					className={
						"flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-muted hover:bg-surface-subtle " +
						(collapsed ? "justify-center" : "")
					}
					title="Log out"
				>
					<LogOut size={16} className="shrink-0" />
					{!collapsed && <span>Log out</span>}
				</button>
			</div>
			<NewTeamDialog open={newTeamOpen} onClose={() => setNewTeamOpen(false)} />
		</div>
	);
}
