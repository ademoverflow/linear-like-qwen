import type { Me } from "@/api/auth";
import type { Activity, Issue, IssueDetail } from "@/api/issues";
import type { Team, TeamMember } from "@/api/teams";

const ISO = "2026-08-22T12:00:00.000Z";
const ISO_RAW = "2026-08-22T12:00:00.123456+00:00";

export const testTeamId = "11111111-1111-4111-8111-111111111111";
export const testUserId = "22222222-2222-4222-8222-222222222222";
export const testStateId = "33333333-3333-4333-8333-333333333333";
export const testIssueId = "44444444-4444-4444-8444-444444444444";

export const meFixture: Me = {
	id: testUserId,
	email: "admin@example.com",
	display_name: "Admin",
	avatar_url: null,
	is_admin: true,
	is_active: true,
	created_at: new Date(ISO),
	memberships: [
		{
			team_id: testTeamId,
			team_key: "ENG",
			team_name: "Engineering",
			role: "owner",
		},
	],
};

export const teamFixture: Team = {
	id: testTeamId,
	name: "Engineering",
	key: "ENG",
	description: null,
	archived_at: null,
	created_at: new Date(ISO),
	updated_at: new Date(ISO),
};

export const memberFixture: TeamMember = {
	id: testUserId,
	display_name: "Admin",
	avatar_url: null,
	role: "owner",
};

export const activityFixture: Activity[] = [
	{
		id: "55555555-5555-4555-8555-555555555555",
		actor_id: testUserId,
		actor_display_name: "Admin",
		kind: "issue.created",
		field: null,
		from_value: null,
		to_value: null,
		created_at: new Date(ISO),
	},
	{
		id: "66666666-6666-4666-8666-666666666666",
		actor_id: testUserId,
		actor_display_name: "Admin",
		kind: "issue.updated",
		field: "title",
		from_value: "Old title",
		to_value: "Set up the core loop",
		created_at: new Date(ISO),
	},
];

export const issueFixture: Issue = {
	id: testIssueId,
	team_id: testTeamId,
	number: 1,
	identifier: "ENG-1",
	title: "Set up the core loop",
	description: null,
	state_id: testStateId,
	state_name: "Backlog",
	state_category: "backlog",
	state_color: "#a2a2a2",
	priority: "none",
	assignee_id: null,
	assignee_display_name: null,
	assignee_avatar_url: null,
	creator_id: testUserId,
	parent_id: null,
	due_date: null,
	estimate: null,
	completed_at: null,
	canceled_at: null,
	archived_at: null,
	created_at: new Date(ISO),
	updated_at: ISO_RAW,
};

export const issueDetailFixture: IssueDetail = {
	...issueFixture,
	description: "# Plan\n\n**bold** and [a link](https://example.com)",
	parent_identifier: null,
	parent_title: null,
};
