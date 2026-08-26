import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { login, type Me, queryKeys } from "@/api/auth";
import { ApiError } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

/** Login screen (brief §7.2.1). Wrong credentials → 401, shown as an alert. */
export function Login() {
	const navigate = useNavigate();
	const queryClient = useQueryClient();
	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");

	const { mutate, error, isPending } = useMutation({
		mutationFn: (input: { email: string; password: string }) => login(input),
		onSuccess: (me: Me) => {
			// Seed the cached user so guarded routes pass immediately.
			queryClient.setQueryData(queryKeys.auth.me(), me);
			navigate({ to: "/" });
		},
	});

	const submit = (event: React.FormEvent) => {
		event.preventDefault();
		if (!email.trim() || !password) return;
		mutate({ email: email.trim(), password });
	};

	return (
		<AuthFrame title="Log in" subtitle="Welcome back to Linear Like Qwen">
			<form onSubmit={submit} className="flex flex-col gap-3">
				<Input
					label="Email"
					type="email"
					value={email}
					onChange={setEmail}
					placeholder="you@example.com"
				/>
				<Input
					label="Password"
					type="password"
					value={password}
					onChange={setPassword}
					placeholder="Your password"
				/>
				{error instanceof ApiError && (
					<p role="alert" className="text-sm text-red-600 dark:text-red-400">
						{error.message}
					</p>
				)}
				<Button type="submit" disabled={isPending}>
					{isPending ? "Logging in…" : "Log in"}
				</Button>
			</form>
			<p className="mt-4 text-center text-sm text-muted">
				No account yet?{" "}
				<Link to="/register" className="text-accent hover:underline">
					Register
				</Link>
			</p>
		</AuthFrame>
	);
}

/** Centered card shared by the auth screens. */
export function AuthFrame({
	title,
	subtitle,
	children,
}: {
	title: string;
	subtitle: string;
	children: React.ReactNode;
}) {
	return (
		<div className="flex min-h-screen items-center justify-center bg-canvas p-4 text-foreground">
			<div className="w-full max-w-sm rounded-lg border border-line bg-surface p-6 shadow-sm">
				<h1 className="text-lg font-semibold">{title}</h1>
				<p className="mb-4 text-sm text-muted">{subtitle}</p>
				{children}
			</div>
		</div>
	);
}
