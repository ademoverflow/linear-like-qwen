import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";

/**
 * Sanitise allowlist for Issue descriptions and Comments (ADR 0007):
 * full GFM (tables, task lists, strikethrough, autolinks), no raw HTML,
 * no `javascript:` URLs.
 */
export const markdownSanitizeSchema = {
	tagNames: [
		"a",
		"blockquote",
		"br",
		"code",
		"del",
		"em",
		"h1",
		"h2",
		"h3",
		"h4",
		"h5",
		"h6",
		"hr",
		"img",
		"input",
		"li",
		"ol",
		"p",
		"pre",
		"s",
		"strong",
		"table",
		"tbody",
		"td",
		"th",
		"thead",
		"tr",
		"ul",
	],
	attributes: {
		a: ["href", "title"],
		img: ["alt", "src", "title"],
		input: ["checked", "disabled", "type"],
		li: ["className"],
		td: ["align"],
		th: ["align"],
		tr: ["align"],
	},
	protocols: {
		href: ["http", "https", "mailto"],
		src: ["http", "https"],
	},
};

/**
 * Markdown renderer (ADR 0007): `react-markdown` + full GFM, sanitised
 * against `markdownSanitizeSchema`. No `dangerouslySetInnerHTML`.
 */
export function Markdown({ content }: { content: string }) {
	return (
		<div className="markdown">
			<ReactMarkdown
				remarkPlugins={[remarkGfm]}
				rehypePlugins={[[rehypeSanitize, markdownSanitizeSchema]]}
			>
				{content}
			</ReactMarkdown>
		</div>
	);
}
