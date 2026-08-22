/**
 * PROTOTYPE (throwaway — delete after the design decision is folded in).
 *
 * Question: list row density + board card anatomy (brief §7.2.2 / §7.2.4).
 * Three structurally different variants of the issue list + board,
 * switchable via ?variant= on /prototype/issue-views.
 * Mock data only — no API, no mutations, no persistence.
 */

import { useNavigate, useSearch } from "@tanstack/react-router";
import {
	AlertOctagon,
	ChevronDown,
	ChevronLeft,
	ChevronRight,
	ChevronsUp,
	ChevronUp,
	Minus,
} from "lucide-react";
import { useEffect, useMemo } from "react";

/* ------------------------------------------------------------------ mock */

type Priority = "none" | "urgent" | "high" | "medium" | "low";
type Category = "backlog" | "unstarted" | "started" | "completed" | "canceled";

interface MockState {
	id: string;
	name: string;
	category: Category;
	color: string;
	position: number;
}

interface MockLabel {
	id: string;
	name: string;
	color: string;
}

interface MockUser {
	id: string;
	name: string;
}

interface MockIssue {
	id: string;
	identifier: string;
	title: string;
	description: string;
	state: MockState;
	priority: Priority;
	assignee: MockUser | null;
	labels: MockLabel[];
	dueDate: string | null;
	estimate: number | null;
}

const STATES: MockState[] = [
	{
		id: "s0",
		name: "Backlog",
		category: "backlog",
		color: "#a2a2a2",
		position: 0,
	},
	{
		id: "s1",
		name: "Todo",
		category: "unstarted",
		color: "#737373",
		position: 1,
	},
	{
		id: "s2",
		name: "In Progress",
		category: "started",
		color: "#f2c94c",
		position: 2,
	},
	{
		id: "s3",
		name: "In Review",
		category: "started",
		color: "#fbc64d",
		position: 3,
	},
	{
		id: "s4",
		name: "Done",
		category: "completed",
		color: "#4cb371",
		position: 4,
	},
	{
		id: "s5",
		name: "Canceled",
		category: "canceled",
		color: "#d98c8c",
		position: 5,
	},
];

const LABELS: MockLabel[] = [
	{ id: "l1", name: "Bug", color: "#e5484d" },
	{ id: "l2", name: "Design", color: "#8e4ec6" },
	{ id: "l3", name: "API", color: "#3b82f6" },
	{ id: "l4", name: "Perf", color: "#f59e0b" },
	{ id: "l5", name: "Docs", color: "#16a34a" },
];

const USERS: MockUser[] = [
	{ id: "u1", name: "Ada Lovelace" },
	{ id: "u2", name: "Ben Chen" },
	{ id: "u3", name: "Divya Pillai" },
	{ id: "u4", name: "Erik Voss" },
];

const ISSUES: MockIssue[] = [
	{
		id: "i1",
		identifier: "ENG-2",
		title: "Fix login redirect loop on expired cookies",
		description:
			"Users land on /login in a loop when the access cookie expires mid-session; refresh should be silent.",
		state: STATES[2],
		priority: "urgent",
		assignee: USERS[0],
		labels: [LABELS[0]],
		dueDate: "Aug 24",
		estimate: 3,
	},
	{
		id: "i2",
		identifier: "ENG-3",
		title: "Migrate database to Postgres 17",
		description:
			"Bump the compose image, verify alembic migrations on the new major version.",
		state: STATES[3],
		priority: "high",
		assignee: USERS[1],
		labels: [LABELS[2]],
		dueDate: null,
		estimate: 8,
	},
	{
		id: "i3",
		identifier: "ENG-8",
		title: "Rate limit the login endpoint",
		description:
			"10 attempts per 15 min per email and per IP, in-process limiter.",
		state: STATES[2],
		priority: "medium",
		assignee: USERS[2],
		labels: [],
		dueDate: null,
		estimate: 2,
	},
	{
		id: "i4",
		identifier: "ENG-10",
		title: "Search index: paginate cursor queries",
		description:
			"Global search blows up past ~500 issues; switch to cursor pagination.",
		state: STATES[2],
		priority: "high",
		assignee: null,
		labels: [LABELS[3]],
		dueDate: null,
		estimate: 5,
	},
	{
		id: "i5",
		identifier: "ENG-4",
		title: "Add keyboard shortcuts (C, /, J/K, S, A, P, L)",
		description:
			"Never fire while focus is in an input, textarea or contenteditable.",
		state: STATES[1],
		priority: "medium",
		assignee: USERS[3],
		labels: [],
		dueDate: "Sep 2",
		estimate: 5,
	},
	{
		id: "i6",
		identifier: "ENG-7",
		title: "Profile avatar upload",
		description: "Upload, crop and serve avatars; fall back to initials.",
		state: STATES[0],
		priority: "low",
		assignee: null,
		labels: [LABELS[1]],
		dueDate: null,
		estimate: 3,
	},
	{
		id: "i7",
		identifier: "ENG-5",
		title: "Refactor issue list pagination",
		description: "Extract the cursor logic into a reusable hook.",
		state: STATES[0],
		priority: "low",
		assignee: USERS[1],
		labels: [LABELS[2]],
		dueDate: null,
		estimate: null,
	},
	{
		id: "i8",
		identifier: "ENG-1",
		title: "Set up CI pipeline",
		description:
			"GitHub Actions: make check + test-core + test-webapp on every PR.",
		state: STATES[4],
		priority: "none",
		assignee: USERS[0],
		labels: [],
		dueDate: null,
		estimate: null,
	},
	{
		id: "i9",
		identifier: "ENG-6",
		title: "Update onboarding copy",
		description: "Align the empty states with the product voice.",
		state: STATES[4],
		priority: "none",
		assignee: USERS[2],
		labels: [LABELS[4]],
		dueDate: null,
		estimate: 1,
	},
	{
		id: "i10",
		identifier: "ENG-9",
		title: "Old billing page",
		description: "Superseded by the pricing revamp; keeping for reference.",
		state: STATES[5],
		priority: "none",
		assignee: null,
		labels: [],
		dueDate: null,
		estimate: null,
	},
];

/* ------------------------------------------------------------- atoms */

function Avatar({ user, size = 20 }: { user: MockUser | null; size?: number }) {
	if (!user) {
		return (
			<div
				className="rounded-full bg-neutral-300 dark:bg-neutral-700"
				style={{ width: size, height: size }}
				role="img"
				aria-label="Unassigned"
			/>
		);
	}
	const initials = user.name
		.split(" ")
		.map((p) => p[0])
		.slice(0, 2)
		.join("");
	return (
		<div
			className="flex items-center justify-center rounded-full bg-indigo-500 font-medium text-white"
			style={{ width: size, height: size, fontSize: size * 0.45 }}
			title={user.name}
		>
			{initials}
		</div>
	);
}

const PRIORITY_STYLE: Record<
	Priority,
	{ icon: typeof Minus; className: string; label: string }
> = {
	none: { icon: Minus, className: "text-neutral-400", label: "No priority" },
	urgent: { icon: AlertOctagon, className: "text-red-500", label: "Urgent" },
	high: {
		icon: ChevronsUp,
		className: "text-neutral-600 dark:text-neutral-300",
		label: "High",
	},
	medium: {
		icon: ChevronUp,
		className: "text-neutral-500 dark:text-neutral-400",
		label: "Medium",
	},
	low: { icon: ChevronDown, className: "text-neutral-400", label: "Low" },
};

function PriorityGlyph({
	priority,
	size = 14,
}: {
	priority: Priority;
	size?: number;
}) {
	const { icon: Icon, className, label } = PRIORITY_STYLE[priority];
	return (
		<span
			className="inline-flex shrink-0"
			role="img"
			title={label}
			aria-label={label}
		>
			<Icon size={size} className={className} />
		</span>
	);
}

function StateDot({ state }: { state: MockState }) {
	return (
		<span
			className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
			style={{ backgroundColor: state.color }}
			aria-hidden
		/>
	);
}

function LabelChip({
	label,
	muted = false,
}: {
	label: MockLabel;
	muted?: boolean;
}) {
	return (
		<span
			className={
				"inline-flex shrink-0 items-center gap-1 rounded px-1.5 text-[11px] " +
				(muted
					? "bg-neutral-100 dark:bg-neutral-800"
					: "bg-neutral-100 dark:bg-neutral-800")
			}
		>
			<span
				className="h-1.5 w-1.5 rounded-full"
				style={{ backgroundColor: label.color }}
			/>
			{label.name}
		</span>
	);
}

function SectionHeading({ children }: { children: string }) {
	return (
		<div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-neutral-400">
			{children}
		</div>
	);
}

/* --------------------------------------------------------- variant A */
/* Flat, dense, table-like list. Minimal board cards (title + footer). */

function VariantA() {
	const groups = STATES.map((s) => ({
		state: s,
		items: ISSUES.filter((i) => i.state.id === s.id),
	}));
	return (
		<div className="flex h-full flex-col gap-6 p-4">
			<div>
				<SectionHeading>List — grouped by state</SectionHeading>
				<div className="overflow-hidden rounded-lg border border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900">
					{groups.map(({ state, items }) => (
						<div key={state.id}>
							<div className="flex items-center gap-2 bg-neutral-50 px-3 py-1.5 dark:bg-neutral-900/60">
								<StateDot state={state} />
								<span className="text-xs font-semibold">{state.name}</span>
								<span className="text-xs text-neutral-400">{items.length}</span>
							</div>
							{items.map((issue) => (
								<div
									key={issue.id}
									className="flex h-8 items-center gap-3 border-t border-neutral-100 px-3 hover:bg-neutral-50 dark:border-neutral-800 dark:hover:bg-neutral-800/60"
								>
									<span className="w-16 shrink-0 font-mono text-xs text-neutral-500">
										{issue.identifier}
									</span>
									<PriorityGlyph priority={issue.priority} />
									<span className="min-w-0 flex-1 truncate text-sm">
										{issue.title}
									</span>
									{issue.labels.slice(0, 2).map((l) => (
										<LabelChip key={l.id} label={l} muted />
									))}
									<Avatar user={issue.assignee} />
								</div>
							))}
						</div>
					))}
				</div>
			</div>
			<div>
				<SectionHeading>Board — minimal cards</SectionHeading>
				<div className="flex gap-3 overflow-x-auto rounded-lg border border-neutral-200 bg-white p-3 dark:border-neutral-800 dark:bg-neutral-900">
					{groups.map(({ state, items }) => (
						<div key={state.id} className="w-44 shrink-0">
							<div className="mb-2 flex items-center gap-2 px-1">
								<StateDot state={state} />
								<span className="text-xs font-semibold">{state.name}</span>
								<span className="text-xs text-neutral-400">{items.length}</span>
							</div>
							<div className="flex flex-col gap-1.5">
								{items.map((issue) => (
									<div
										key={issue.id}
										className="cursor-grab rounded border border-neutral-200 bg-white p-2 shadow-sm dark:border-neutral-700 dark:bg-neutral-800"
									>
										<div className="truncate text-xs font-medium">
											{issue.title}
										</div>
										<div className="mt-1.5 flex items-center justify-between">
											<PriorityGlyph priority={issue.priority} size={12} />
											<Avatar user={issue.assignee} size={16} />
										</div>
									</div>
								))}
							</div>
						</div>
					))}
				</div>
			</div>
		</div>
	);
}

/* --------------------------------------------------------- variant B */
/* Comfortable card stack list. Rich board cards (title, snippet,
   labels, footer with priority, due date and avatar). */

function VariantB() {
	const groups = STATES.map((s) => ({
		state: s,
		items: ISSUES.filter((i) => i.state.id === s.id),
	}));
	return (
		<div className="flex h-full flex-col gap-6 p-4">
			<div>
				<SectionHeading>List — card stack</SectionHeading>
				<div className="flex max-w-2xl flex-col gap-2">
					{ISSUES.map((issue) => (
						<div
							key={issue.id}
							className="rounded-lg border border-neutral-200 bg-white p-3 shadow-sm hover:shadow dark:border-neutral-800 dark:bg-neutral-900"
						>
							<div className="flex items-center gap-2">
								<span className="font-mono text-xs text-neutral-500">
									{issue.identifier}
								</span>
								<span className="min-w-0 flex-1 truncate text-sm font-medium">
									{issue.title}
								</span>
								<StateDot state={issue.state} />
							</div>
							<div className="mt-2 flex items-center gap-2">
								<PriorityGlyph priority={issue.priority} />
								{issue.labels.map((l) => (
									<LabelChip key={l.id} label={l} />
								))}
								{issue.dueDate && (
									<span className="text-[11px] text-neutral-500">
										due {issue.dueDate}
									</span>
								)}
								<span className="flex-1" />
								<Avatar user={issue.assignee} />
							</div>
						</div>
					))}
				</div>
			</div>
			<div>
				<SectionHeading>Board — rich cards</SectionHeading>
				<div className="flex gap-3 overflow-x-auto rounded-lg border border-neutral-200 bg-white p-3 dark:border-neutral-800 dark:bg-neutral-900">
					{groups.map(({ state, items }) => (
						<div key={state.id} className="w-60 shrink-0">
							<div className="mb-2 flex items-center gap-2 px-1">
								<StateDot state={state} />
								<span className="text-xs font-semibold">{state.name}</span>
								<span className="text-xs text-neutral-400">{items.length}</span>
							</div>
							<div className="flex flex-col gap-2">
								{items.map((issue) => (
									<div
										key={issue.id}
										className="cursor-grab rounded-lg border border-neutral-200 bg-white p-3 shadow-sm dark:border-neutral-700 dark:bg-neutral-800"
									>
										<div className="text-sm font-medium leading-snug">
											{issue.title}
										</div>
										<div className="mt-1 line-clamp-1 text-xs text-neutral-500">
											{issue.description}
										</div>
										{issue.labels.length > 0 && (
											<div className="mt-2 flex flex-wrap gap-1">
												{issue.labels.map((l) => (
													<LabelChip key={l.id} label={l} muted />
												))}
											</div>
										)}
										<div className="mt-2 flex items-center gap-2">
											<PriorityGlyph priority={issue.priority} size={12} />
											{issue.dueDate && (
												<span className="text-[11px] text-neutral-500">
													{issue.dueDate}
												</span>
											)}
											<span className="flex-1" />
											<Avatar user={issue.assignee} size={18} />
										</div>
									</div>
								))}
							</div>
						</div>
					))}
				</div>
			</div>
		</div>
	);
}

/* --------------------------------------------------------- variant C */
/* Grouped list with sticky headers; the row drops everything that the
   grouping already says (no state column). Ultra-minimal title-only
   board cards. */

function VariantC() {
	const groups = STATES.map((s) => ({
		state: s,
		items: ISSUES.filter((i) => i.state.id === s.id),
	}));
	return (
		<div className="flex h-full flex-col gap-6 p-4">
			<div>
				<SectionHeading>
					List — grouped, sticky headers, sparse rows
				</SectionHeading>
				<div className="max-w-2xl">
					{groups.map(({ state, items }) => (
						<div key={state.id} className="mb-4">
							<div className="sticky top-0 z-10 flex items-center gap-2 bg-neutral-50/95 px-2 py-1 backdrop-blur dark:bg-neutral-950/95">
								<StateDot state={state} />
								<span className="text-xs font-semibold">{state.name}</span>
								<span className="text-xs text-neutral-400">{items.length}</span>
							</div>
							{items.map((issue) => (
								<div
									key={issue.id}
									className="flex h-9 items-center gap-3 px-2 hover:bg-neutral-100 dark:hover:bg-neutral-800/60"
								>
									<span className="w-16 shrink-0 font-mono text-xs text-neutral-500">
										{issue.identifier}
									</span>
									<span className="min-w-0 flex-1 truncate text-sm">
										{issue.title}
									</span>
									<Avatar user={issue.assignee} size={18} />
								</div>
							))}
						</div>
					))}
				</div>
			</div>
			<div>
				<SectionHeading>Board — title-only cards</SectionHeading>
				<div className="flex gap-2 overflow-x-auto rounded-lg border border-neutral-200 bg-white p-3 dark:border-neutral-800 dark:bg-neutral-900">
					{groups.map(({ state, items }) => (
						<div key={state.id} className="w-40 shrink-0">
							<div className="mb-2 flex items-center gap-2 px-1">
								<StateDot state={state} />
								<span className="text-xs font-semibold">{state.name}</span>
								<span className="text-xs text-neutral-400">{items.length}</span>
							</div>
							<div className="flex flex-col gap-1">
								{items.map((issue) => (
									<div
										key={issue.id}
										className="relative cursor-grab rounded bg-neutral-100 px-2.5 py-1.5 hover:bg-neutral-200 dark:bg-neutral-800 dark:hover:bg-neutral-700"
									>
										<div className="pr-5 text-xs font-medium leading-snug">
											{issue.title}
										</div>
										<div className="absolute right-1.5 top-1.5">
											<Avatar user={issue.assignee} size={14} />
										</div>
									</div>
								))}
							</div>
						</div>
					))}
				</div>
			</div>
		</div>
	);
}

/* --------------------------------------------------------- switcher */

const VARIANTS = {
	a: { component: VariantA, name: "Dense table + minimal cards" },
	b: { component: VariantB, name: "Card stack + rich cards" },
	c: { component: VariantC, name: "Grouped sparse + title-only cards" },
} as const;

type VariantKey = keyof typeof VARIANTS;

const VARIANT_KEYS = Object.keys(VARIANTS) as VariantKey[];

function PrototypeSwitcher({ current }: { current: VariantKey }) {
	const navigate = useNavigate();

	const go = (direction: 1 | -1) => {
		const next =
			VARIANT_KEYS[
				(VARIANT_KEYS.indexOf(current) + direction + VARIANT_KEYS.length) %
					VARIANT_KEYS.length
			];
		navigate({
			to: "/prototype/issue-views",
			search: { variant: next },
			replace: true,
		});
	};

	useEffect(() => {
		const move = (direction: 1 | -1) => {
			const next =
				VARIANT_KEYS[
					(VARIANT_KEYS.indexOf(current) + direction + VARIANT_KEYS.length) %
						VARIANT_KEYS.length
				];
			navigate({
				to: "/prototype/issue-views",
				search: { variant: next },
				replace: true,
			});
		};
		const onKey = (e: KeyboardEvent) => {
			const el = document.activeElement;
			const inField =
				el instanceof HTMLElement &&
				(el.tagName === "INPUT" ||
					el.tagName === "TEXTAREA" ||
					el.isContentEditable);
			if (inField) return;
			if (e.key === "ArrowLeft") move(-1);
			if (e.key === "ArrowRight") move(1);
		};
		window.addEventListener("keydown", onKey);
		return () => window.removeEventListener("keydown", onKey);
	}, [current, navigate]);

	if (import.meta.env.PROD) return null;

	return (
		<div className="fixed bottom-4 left-1/2 z-50 flex -translate-x-1/2 items-center gap-1 rounded-full bg-neutral-900 p-1 text-white shadow-lg ring-1 ring-white/20 dark:bg-neutral-100 dark:text-neutral-900 dark:ring-black/20">
			<button
				type="button"
				aria-label="Previous variant"
				className="rounded-full p-2 hover:bg-white/10 dark:hover:bg-black/10"
				onClick={() => go(-1)}
			>
				<ChevronLeft size={16} />
			</button>
			<span className="px-2 text-xs font-medium">
				{current.toUpperCase()} · {VARIANTS[current].name}
			</span>
			<button
				type="button"
				aria-label="Next variant"
				className="rounded-full p-2 hover:bg-white/10 dark:hover:bg-black/10"
				onClick={() => go(1)}
			>
				<ChevronRight size={16} />
			</button>
		</div>
	);
}

/* ------------------------------------------------------------- route */

function IssueViewsPrototype() {
	const variantParam = useSearch({
		from: "/prototype/issue-views",
		select: (s) => (s.variant as VariantKey | undefined) ?? "a",
	});
	const variant = VARIANTS[variantParam] ? variantParam : "a";
	const Content = useMemo(() => VARIANTS[variant].component, [variant]);

	return (
		<div className="h-screen overflow-y-auto bg-neutral-50 text-neutral-900 dark:bg-neutral-950 dark:text-neutral-100">
			<div className="sticky top-0 z-20 border-b border-neutral-200 bg-white/90 px-4 py-2 backdrop-blur dark:border-neutral-800 dark:bg-neutral-900/90">
				<span className="text-sm font-semibold">
					ENG › Prototype: issue list density + board card anatomy
				</span>
				<span className="ml-2 text-xs text-neutral-400">
					throwaway — mock data, no API
				</span>
			</div>
			<Content />
			<PrototypeSwitcher current={variant} />
		</div>
	);
}

export default IssueViewsPrototype;
