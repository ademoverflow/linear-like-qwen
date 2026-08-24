import { describe, expect, it } from "vitest";

import type { Comment } from "@/api/comments";
import type { Activity } from "@/api/issues";
import { commentFixture } from "../test/fixtures";
import { type FeedEntry, mergeFeed } from "./feed";

let nextId = 1;

function makeId(prefix: string): string {
	nextId += 1;
	return `${prefix.repeat(8)}-${prefix.repeat(4)}-4${prefix.repeat(3)}-8${prefix.repeat(
		3,
	)}-${String(nextId).padStart(12, prefix)}`;
}

function activity(kind: string, overrides: Partial<Activity> = {}): Activity {
	return {
		id: makeId("a"),
		actor_id: "22222222-2222-4222-8222-222222222222",
		actor_display_name: "Admin",
		kind,
		field: null,
		from_value: null,
		to_value: null,
		created_at: new Date("2026-08-22T12:00:00.000Z"),
		...overrides,
	};
}

function comment(body: string, overrides: Partial<Comment> = {}): Comment {
	return {
		...commentFixture,
		id: makeId("b"),
		body,
		...overrides,
	};
}

function types(entries: FeedEntry[]): string[] {
	return entries.map((entry) => entry.type);
}

function commentAt(entries: FeedEntry[], index: number): Comment {
	const entry = entries[index];
	if (entry.type !== "comment")
		throw new Error(`entry ${index} is not a comment`);
	return entry.comment;
}

function activityAt(entries: FeedEntry[], index: number): Activity {
	const entry = entries[index];
	if (entry.type !== "activity")
		throw new Error(`entry ${index} is not an activity`);
	return entry.activity;
}

describe("mergeFeed", () => {
	it("returns the Activity list unchanged when there are no Comments", () => {
		const first = activity("issue.created");
		const second = activity("issue.updated");
		const entries = mergeFeed([first, second], []);
		expect(types(entries)).toEqual(["activity", "activity"]);
		expect(activityAt(entries, 0)).toBe(first);
		expect(activityAt(entries, 1)).toBe(second);
	});

	it("replaces the comment.created row with the Comment card in place", () => {
		const created = activity("issue.created");
		const updated = activity("issue.updated");
		const hello = comment("hello");
		const entries = mergeFeed(
			[created, activity("comment.created"), updated],
			[hello],
		);
		expect(types(entries)).toEqual(["activity", "comment", "activity"]);
		expect(activityAt(entries, 0)).toBe(created);
		expect(commentAt(entries, 1)).toBe(hello);
		expect(activityAt(entries, 2)).toBe(updated);
	});

	it("keeps multiple Comments in creation order at their rows", () => {
		const first = comment("first");
		const second = comment("second");
		const entries = mergeFeed(
			[
				activity("issue.created"),
				activity("comment.created"),
				activity("comment.created"),
			],
			[first, second],
		);
		expect(types(entries)).toEqual(["activity", "comment", "comment"]);
		expect(commentAt(entries, 1)).toBe(first);
		expect(commentAt(entries, 2)).toBe(second);
	});

	it("renders comment.updated and comment.deleted rows as Activity lines", () => {
		const entries = mergeFeed(
			[
				activity("comment.created"),
				activity("issue.updated"),
				activity("comment.updated"),
				activity("comment.deleted"),
			],
			[comment("v1")],
		);
		expect(types(entries)).toEqual([
			"comment",
			"activity",
			"activity",
			"activity",
		]);
		expect(activityAt(entries, 2).kind).toBe("comment.updated");
		expect(activityAt(entries, 3).kind).toBe("comment.deleted");
	});

	it("appends Comments without a surviving comment.created row (defensive)", () => {
		const orphan = comment("orphan");
		const entries = mergeFeed([activity("issue.created")], [orphan]);
		expect(types(entries)).toEqual(["activity", "comment"]);
		expect(commentAt(entries, 1)).toBe(orphan);
	});

	it("pairs comment.created rows to Comments by comment_id", () => {
		const first = comment("first");
		const second = comment("second");
		// The rows' comment_ids point at the Comments out of creation
		// order (e.g. tied created_at timestamps): the cards follow the
		// rows, not the creation order.
		const rows = [
			activity("comment.created", { comment_id: second.id }),
			activity("comment.created", { comment_id: first.id }),
		];
		const entries = mergeFeed(rows, [first, second]);
		expect(types(entries)).toEqual(["comment", "comment"]);
		expect(commentAt(entries, 0)).toBe(second);
		expect(commentAt(entries, 1)).toBe(first);
	});
});
