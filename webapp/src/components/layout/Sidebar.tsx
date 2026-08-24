import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useRouter } from "@tanstack/react-router";
import {
	LogOut,
	PanelLeftClose,
	PanelLeftOpen,
	Plus,
	Shield,
} from "lucide-react";
import { useState } from "react";
import { logout, queryKeys } from "@/api/auth";
import { listTeams } from "@/api/teams";
import { NewTeamDialog } from "@/components/teams/NewTeamDialog";
import { env } from "@/env";
import { useCurrentUser } from "@/hooks/use-current-user";

const STORAGE_KEY = "sidebar-collapsed";

/**
 * Collapsible left sidebar (brief §7.1): workspace name, Teams section and
 * logout. Teams link to their Issues list.
 */
export function Sidebar() {
	const [collapsed, setCollapsed] = useState(() => {
		try {
			return localStorage.getItem(STORAGE_KEY) === "1";
		} catch {
			return false;
		}
	});
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
				"flex h-full shrink-0 flex-col border-r border-neutral-200 bg-white transition-[width] dark:border-neutral-800 dark:bg-neutral-900 " +
				(collapsed ? "w-14" : "w-60")
			}
		>
			<div
				className={
					"flex h-12 items-center border-b border-neutral-200 dark:border-neutral-800 " +
					(collapsed ? "justify-center" : "justify-between px-3")
				}
			>
				<span
					className={
						"truncate text-sm font-semibold text-neutral-900 dark:text-neutral-100 " +
						(collapsed ? "sr-only" : "")
					}
				>
					{env.VITE_APP_TITLE ?? "Linear Like Qwen"}
				</span>
				<button
					type="button"
					onClick={toggle}
					aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
					className="rounded p-1.5 text-neutral-400 hover:bg-neutral-100 hover:text-neutral-600 dark:hover:bg-neutral-800"
				>
					{collapsed ? (
						<PanelLeftOpen size={16} />
					) : (
						<PanelLeftClose size={16} />
					)}
				</button>
			</div>

			<nav className="flex-1 overflow-y-auto p-2" aria-label="Teams">
				{!collapsed && (
					<div className="mb-1 px-2 text-[11px] font-semibold uppercase tracking-wider text-neutral-400">
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
								className={
									"flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-neutral-700 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800 " +
									(collapsed ? "justify-center" : "")
								}
							>
								<span
									className={
										"shrink-0 font-mono text-xs text-neutral-500 " +
										(collapsed ? "" : "w-10")
									}
								>
									{team.key}
								</span>
								{!collapsed && <span className="truncate">{team.name}</span>}
							</Link>
							{!collapsed && (
								<div className="ml-7 mt-0.5 flex flex-col gap-0.5 border-l border-neutral-200 pl-2 dark:border-neutral-800">
									<Link
										to="/teams/$teamKey/board"
										params={{ teamKey: team.key }}
										className="rounded px-2 py-1 text-xs text-neutral-500 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-800"
									>
										Board
									</Link>
								</div>
							)}
						</li>
					))}
				</ul>
			</nav>

			<div className="border-t border-neutral-200 p-2 dark:border-neutral-800">
				{me?.is_admin && (
					<Link
						to="/admin"
						title="Admin"
						className={
							"flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-neutral-600 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-800 " +
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
							"flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-neutral-600 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-800 " +
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
						"flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-neutral-600 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-800 " +
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
