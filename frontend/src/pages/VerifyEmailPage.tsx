import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { AuthShell } from "../components/auth/AuthShell";
import { usePageTitle } from "../lib/usePageTitle";

/** Opened from the emailed link: /verify-email?token=… */
export default function VerifyEmailPage() {
  usePageTitle("Confirm email");
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const q = useQuery({
    queryKey: ["verify-email", token],
    enabled: token !== "",
    retry: false,
    staleTime: Infinity,
    queryFn: () =>
      api.post<{ status: string }>(
        "/auth/verify-email/",
        { token },
        { skipAuthRetry: true },
      ),
  });
  return (
    <AuthShell title="Confirm your email">
      <div aria-live="polite" className="space-y-3 text-sm">
        {!token && (
          <p role="alert" className="text-red-700">
            This link is incomplete. Open the link from the email again.
          </p>
        )}
        {token !== "" && q.isPending && <p>Confirming…</p>}
        {q.isError && (
          <>
            <p role="alert" className="text-red-700">
              {q.error instanceof ApiError
                ? q.error.message
                : "Could not confirm your address."}
            </p>
            <p>
              <Link to="/login">Sign in</Link> and choose "Resend the
              confirmation email" to get a new link.
            </p>
          </>
        )}
        {q.data && (
          <>
            <p role="status" className="text-risk-low">
              Your email address is confirmed.
            </p>
            {q.data.status === "pending_approval" ? (
              <p>
                An administrator now has to approve your account. You will get
                an email as soon as that happens.
              </p>
            ) : (
              <p>
                You can <Link to="/login">sign in</Link> now.
              </p>
            )}
          </>
        )}
      </div>
    </AuthShell>
  );
}
