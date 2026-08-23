import type { Me } from "@/api/auth";
import type { Issue } from "@/api/issues";
import type { Team } from "@/api/teams";

const ISO = "2026-08-22T12:00:00.000Z";

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
	updated_at: new Date(ISO),
};
