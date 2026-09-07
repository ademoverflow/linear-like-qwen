import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Markdown } from "@/lib/markdown";

/**
 * Markdown editor with Write/Preview modes (ADR 0007). The shared shape
 * behind the description editor, the Comment editor and the Comment
 * composer (ticket 06).
 */
export function MarkdownEditor({
	initial,
	ariaLabel,
	rows = 4,
	placeholder,
	maxLength,
	onSave,
	saveLabel = "Save",
	saveDisabled = false,
	disableEmpty = false,
	onCancel,
	actionAlign = "start",
}: {
	initial: string;
	ariaLabel: string;
	rows?: number;
	placeholder?: string;
	maxLength?: number;
	onSave: (draft: string) => void;
	saveLabel?: string;
	saveDisabled?: boolean;
	disableEmpty?: boolean;
	onCancel?: () => void;
	actionAlign?: "start" | "end";
}) {
	const [mode, setMode] = useState<"write" | "preview">("write");
	const [draft, setDraft] = useState(initial);
	const empty = draft.trim().length === 0;

	return (
		<div className="flex flex-col gap-2">
			<div className="flex items-center gap-1">
				<Button
					variant={mode === "write" ? "primary" : "secondary"}
					onClick={() => setMode("write")}
				>
					Write
				</Button>
				<Button
					variant={mode === "preview" ? "primary" : "secondary"}
					onClick={() => setMode("preview")}
				>
					Preview
				</Button>
			</div>
			{mode === "write" ? (
				<textarea
					aria-label={ariaLabel}
					value={draft}
					rows={rows}
					maxLength={maxLength}
					placeholder={placeholder}
					onChange={(event) => setDraft(event.target.value)}
					className="w-full rounded-md border border-neutral-300 bg-surface p-2 text-sm text-foreground focus:border-accent dark:border-neutral-700"
				/>
			) : (
				<div className="rounded-md border border-line p-3">
					{empty ? (
						<p className="text-sm text-muted">Nothing to preview.</p>
					) : (
						<Markdown content={draft} />
					)}
				</div>
			)}
			<div
				className={
					actionAlign === "end" ? "flex justify-end gap-2" : "flex gap-2"
				}
			>
				<Button
					onClick={() => onSave(draft)}
					disabled={saveDisabled || (disableEmpty && empty)}
				>
					{saveLabel}
				</Button>
				{onCancel ? (
					<Button variant="secondary" onClick={onCancel}>
						Cancel
					</Button>
				) : null}
			</div>
		</div>
	);
}
