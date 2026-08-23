import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { getAuthStatus, type Me, queryKeys, register } from "@/api/auth";
import { ApiError } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { AuthFrame } from "./Login";

/**
 * Registration screen: while the user base is empty the first registrant
 * bootstraps the Workspace (becomes Admin); afterwards an Invitation token
 * is required (token verification lands with the invitations ticket).
 */
export function Register() {
	const navigate = useNavigate();
	const queryClient = useQueryClient();
	const statusQuery = useQuery({
		queryKey: queryKeys.auth.status(),
		queryFn: getAuthStatus,
	});
	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");
	const [token, setToken] = useState("");

	const bootstrapOpen = statusQuery.data?.bootstrap_open ?? null;

	const { mutate, error, isPending } = useMutation({
		mutationFn: (input: { email: string; password: string; token?: string }) =>
			register(input),
		onSuccess: (me: Me) => {
			queryClient.setQueryData(queryKeys.auth.me(), me);
			navigate({ to: "/" });
		},
	});

	const submit = (event: React.FormEvent) => {
		event.preventDefault();
		if (!email.trim() || !password) return;
		mutate({
			email: email.trim(),
			password,
			...(token.trim() ? { token: token.trim() } : {}),
		});
	};

	return (
		<AuthFrame
			title={
				bootstrapOpen === null
					? "Register"
					: bootstrapOpen
						? "Create your account"
						: "Join with an invitation"
			}
			subtitle={
				bootstrapOpen === null
					? "Checking whether registration is open…"
					: bootstrapOpen
						? "You are the first user — this account becomes the Workspace Admin."
						: "Registration requires an Invitation token from a workspace Admin."
			}
		>
			{statusQuery.isLoading ? (
				<div className="flex flex-col gap-3">
					<div className="h-9 animate-pulse rounded-md bg-neutral-200 dark:bg-neutral-800" />
					<div className="h-9 animate-pulse rounded-md bg-neutral-200 dark:bg-neutral-800" />
				</div>
			) : (
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
						placeholder="At least 8 characters"
					/>
					{bootstrapOpen === false && (
						<Input
							label="Invitation token"
							value={token}
							onChange={setToken}
							placeholder="Your invitation token"
						/>
					)}
					{error instanceof ApiError && (
						<p role="alert" className="text-sm text-red-600 dark:text-red-400">
							{error.message}
						</p>
					)}
					<Button type="submit" disabled={isPending}>
						{isPending ? "Creating…" : "Register"}
					</Button>
				</form>
			)}
			<p className="mt-4 text-center text-sm text-neutral-500">
				Already have an account?{" "}
				<Link to="/login" className="text-accent hover:underline">
					Log in
				</Link>
			</p>
		</AuthFrame>
	);
}
