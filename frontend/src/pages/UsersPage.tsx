import { PageHero } from "../components/scenes/PageHero";
import {
  Card3D,
  CardGrid,
  Chip,
  Initials,
  useViewMode,
  ViewToggle,
} from "../components/ui/cards";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { api, ApiError } from "../api/client";
import type { Paginated, PermissionInfo, Role, User } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Button } from "../components/ui/Button";
import { Dialog } from "../components/ui/Dialog";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/states";
import { useToast } from "../components/ui/Toast";

function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    const details = Object.entries(e.details)
      .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(" ") : String(v)}`)
      .join(" · ");
    return details || e.message;
  }
  return "Unexpected error";
}

export default function UsersPage() {
  const [tab, setTab] = useState<"users" | "roles">("users");
  const { can } = useAuth();
  return (
    <section>
      <PageHero
        eyebrow="Govern"
        title="User management"
        tone="indigo"
        scene="people"
      />
      <div role="tablist" className="mt-4 flex gap-2 border-b border-slate-200">
        {(["users", "roles"] as const).map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            disabled={t === "roles" && !can("roles.read")}
            onClick={() => setTab(t)}
            className={`px-3 py-2 text-sm capitalize ${tab === t ? "border-b-2 border-slate-900 font-medium" : "text-slate-600"}`}
          >
            {t}
          </button>
        ))}
      </div>
      <div className="mt-4">
        {tab === "users" ? <UsersTab /> : <RolesTab />}
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ users
const createSchema = z.object({
  email: z.string().min(1, "Email is required").email("Enter a valid email"),
  full_name: z.string().min(1, "Name is required"),
  role: z.string().min(1, "Select a role"),
  password: z.string().min(12, "At least 12 characters"),
});
type CreateValues = z.infer<typeof createSchema>;

function PendingApprovals() {
  const { can } = useAuth();
  const toast = useToast();
  const qc = useQueryClient();
  const [roleFor, setRoleFor] = useState<Record<number, string>>({});
  const pending = useQuery({
    queryKey: ["users", "pending"],
    enabled: can("users.update"),
    queryFn: ({ signal }) =>
      api.get<Paginated<User>>(
        "/users/?approval_status=pending&page_size=50",
        signal,
      ),
  });
  const roles = useQuery({
    queryKey: ["roles"],
    queryFn: ({ signal }) => api.get<Role[]>("/roles/", signal),
  });
  const done = () => {
    void qc.invalidateQueries({ queryKey: ["users"] });
  };
  const approve = useMutation({
    mutationFn: ({ id, role }: { id: number; role: string }) =>
      api.post<User>(`/users/${id}/approve/`, { role }),
    onSuccess: () => {
      toast("success", "Account approved; the user was notified by email");
      done();
    },
    onError: (e) => toast("error", errorText(e)),
  });
  const reject = useMutation({
    mutationFn: (id: number) => api.post<User>(`/users/${id}/reject/`),
    onSuccess: () => {
      toast("success", "Account rejected");
      done();
    },
    onError: (e) => toast("error", errorText(e)),
  });
  const list = pending.data?.results ?? [];
  if (!can("users.update") || list.length === 0) return null;
  const assignable = (roles.data ?? []).filter(
    (r) => r.name !== "pending_user",
  );
  return (
    <section
      aria-labelledby="pending-title"
      className="mb-6 rounded-2xl border border-amber-400/40 bg-amber-400/5 p-4"
    >
      <h2 id="pending-title" className="text-base font-semibold">
        Waiting for approval ({pending.data?.count ?? list.length})
      </h2>
      <p className="text-xs text-slate-500">
        These people registered themselves. Approve with a role, or reject.
        Accounts that have not confirmed their email cannot be approved yet.
      </p>
      <div className="stagger mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
        {list.map((u) => {
          const role = roleFor[u.id] ?? "";
          return (
            <div
              key={u.id}
              className="flex min-w-0 flex-col gap-2 rounded-xl border border-indigo-400/20 bg-white/[0.04] p-3"
            >
              <div className="flex flex-wrap items-center gap-3">
                <Initials text={u.email} />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{u.full_name}</p>
                  <p className="truncate text-xs text-slate-500">{u.email}</p>
                </div>
                <span className="ml-auto">
                  <Chip tone={u.email_verified ? "green" : "amber"}>
                    {u.email_verified
                      ? "email confirmed"
                      : "email not confirmed"}
                  </Chip>
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <select
                  aria-label={`Role for ${u.email}`}
                  value={role}
                  onChange={(e) =>
                    setRoleFor({ ...roleFor, [u.id]: e.target.value })
                  }
                  className="rounded-md border border-slate-300 px-2 py-1"
                >
                  <option value="">Choose a role…</option>
                  {assignable.map((r) => (
                    <option key={r.id} value={r.name}>
                      {r.label}
                    </option>
                  ))}
                </select>
                <Button
                  aria-label={`Approve ${u.email}`}
                  disabled={!role || !u.email_verified || approve.isPending}
                  onClick={() => approve.mutate({ id: u.id, role })}
                >
                  Approve
                </Button>
                <Button
                  variant="danger"
                  aria-label={`Reject ${u.email}`}
                  disabled={reject.isPending}
                  onClick={() => reject.mutate(u.id)}
                >
                  Reject
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function UsersTab() {
  const { can, user: me } = useAuth();
  const toast = useToast();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [view, setView] = useViewMode("users");
  const [creating, setCreating] = useState(false);
  const [toggling, setToggling] = useState<User | null>(null);
  const [resetting, setResetting] = useState<User | null>(null);

  const params = new URLSearchParams({ page: String(page) });
  if (search) params.set("search", search);
  const users = useQuery({
    queryKey: ["users", search, page],
    queryFn: ({ signal }) =>
      api.get<Paginated<User>>(`/users/?${params.toString()}`, signal),
  });
  const roles = useQuery({
    queryKey: ["roles"],
    queryFn: ({ signal }) => api.get<Role[]>("/roles/", signal),
  });

  const patch = useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: number;
      body: Partial<Pick<User, "role" | "is_active">>;
    }) => api.patch<User>(`/users/${id}/`, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["users"] });
      toast("success", "User updated");
    },
    onError: (e) => toast("error", errorText(e)),
  });

  return (
    <div>
      <PendingApprovals />
      <div className="flex items-end justify-between gap-3">
        <label className="text-sm">
          Search
          <input
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Name or email"
            className="mt-1 block rounded-md border border-slate-300 px-2 py-1"
          />
        </label>
        {can("users.create") && (
          <Button onClick={() => setCreating(true)}>Add user</Button>
        )}
      </div>

      <div className="mt-4">
        {users.isPending && <LoadingState />}
        {users.isError && (
          <ErrorState
            message={users.error.message}
            onRetry={() => void users.refetch()}
          />
        )}
        {users.data && users.data.results.length === 0 && (
          <EmptyState title="No users found" />
        )}
        {users.data && users.data.results.length > 0 && (
          <>
            <div className="space-y-3">
              <ViewToggle mode={view} onChange={setView} />
              {view === "cards" ? (
                <CardGrid min="20rem">
                  {users.data.results.map((u) => (
                    <Card3D key={u.id} tone={u.is_active ? "indigo" : "slate"}>
                      <div className="flex items-center gap-3">
                        <Initials text={u.email} />
                        <div className="min-w-0">
                          <h2 className="truncate text-sm font-semibold text-slate-800">
                            {u.full_name}
                          </h2>
                          <p className="truncate text-xs text-slate-500">
                            {u.email}
                          </p>
                        </div>
                      </div>
                      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
                        {can("users.update") &&
                        roles.data &&
                        u.id !== me?.id ? (
                          <select
                            aria-label={`Role for ${u.email}`}
                            value={u.role}
                            onChange={(e) =>
                              patch.mutate({
                                id: u.id,
                                body: { role: e.target.value },
                              })
                            }
                            className="rounded-md border border-slate-300 px-1 py-0.5"
                          >
                            {roles.data.map((r) => (
                              <option key={r.id} value={r.name}>
                                {r.label}
                              </option>
                            ))}
                          </select>
                        ) : (
                          <Chip tone="violet">{u.role_label}</Chip>
                        )}
                        <Chip tone={u.is_active ? "green" : "slate"}>
                          {u.is_active ? "Active" : "Inactive"}
                        </Chip>
                      </div>
                      <p className="mt-2 text-xs text-slate-500">
                        Last login:{" "}
                        {u.last_login
                          ? new Date(u.last_login).toLocaleString()
                          : "Never"}
                      </p>
                      {can("users.update") && u.id !== me?.id && (
                        <div className="mt-auto flex flex-wrap gap-2 pt-3">
                          <Button
                            variant="secondary"
                            onClick={() => setResetting(u)}
                          >
                            Reset password
                          </Button>
                          <Button
                            variant={u.is_active ? "danger" : "secondary"}
                            onClick={() => setToggling(u)}
                          >
                            {u.is_active ? "Deactivate" : "Activate"}
                          </Button>
                        </div>
                      )}
                    </Card3D>
                  ))}
                </CardGrid>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="border-b border-slate-300 text-slate-600">
                      <tr>
                        <th className="py-2">Name</th>
                        <th>Email</th>
                        <th>Role</th>
                        <th>Status</th>
                        <th>Last login</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {users.data.results.map((u) => (
                        <tr key={u.id} className="border-b border-slate-100">
                          <td className="py-2">{u.full_name}</td>
                          <td>{u.email}</td>
                          <td>
                            {can("users.update") &&
                            roles.data &&
                            u.id !== me?.id ? (
                              <select
                                aria-label={`Role for ${u.email}`}
                                value={u.role}
                                onChange={(e) =>
                                  patch.mutate({
                                    id: u.id,
                                    body: { role: e.target.value },
                                  })
                                }
                                className="rounded-md border border-slate-300 px-1 py-0.5"
                              >
                                {roles.data.map((r) => (
                                  <option key={r.id} value={r.name}>
                                    {r.label}
                                  </option>
                                ))}
                              </select>
                            ) : (
                              u.role_label
                            )}
                          </td>
                          <td>
                            <span
                              className={
                                u.is_active ? "text-risk-low" : "text-slate-500"
                              }
                            >
                              {u.is_active ? "Active" : "Inactive"}
                            </span>
                          </td>
                          <td>
                            {u.last_login
                              ? new Date(u.last_login).toLocaleString()
                              : "Never"}
                          </td>
                          <td className="space-x-2 text-right">
                            {can("users.update") && u.id !== me?.id && (
                              <>
                                <Button
                                  variant="secondary"
                                  onClick={() => setResetting(u)}
                                >
                                  Reset password
                                </Button>
                                <Button
                                  variant={u.is_active ? "danger" : "secondary"}
                                  onClick={() => setToggling(u)}
                                >
                                  {u.is_active ? "Deactivate" : "Activate"}
                                </Button>
                              </>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
            <div className="mt-3 flex items-center gap-3 text-sm">
              <Button
                variant="secondary"
                disabled={!users.data.previous}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </Button>
              <span>
                Page {page} · {users.data.count} users
              </span>
              <Button
                variant="secondary"
                disabled={!users.data.next}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </>
        )}
      </div>

      <CreateUserDialog
        open={creating}
        roles={roles.data ?? []}
        onClose={() => setCreating(false)}
      />

      <Dialog
        open={toggling !== null}
        title={toggling?.is_active ? "Deactivate user?" : "Activate user?"}
        onClose={() => setToggling(null)}
      >
        <p className="text-sm">
          {toggling?.is_active
            ? `${toggling.email} will be signed out everywhere and unable to log in.`
            : `${toggling?.email ?? ""} will be able to log in again.`}
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setToggling(null)}>
            Cancel
          </Button>
          <Button
            onClick={() => {
              if (toggling)
                patch.mutate({
                  id: toggling.id,
                  body: { is_active: !toggling.is_active },
                });
              setToggling(null);
            }}
          >
            Confirm
          </Button>
        </div>
      </Dialog>

      <ResetPasswordDialog
        user={resetting}
        onClose={() => setResetting(null)}
      />
    </div>
  );
}

function CreateUserDialog({
  open,
  roles,
  onClose,
}: {
  open: boolean;
  roles: Role[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<CreateValues>({
    resolver: zodResolver(createSchema),
    defaultValues: { role: "" },
  });

  const submit = async (v: CreateValues) => {
    setServerError(null);
    try {
      await api.post<User>("/users/", v);
      await qc.invalidateQueries({ queryKey: ["users"] });
      toast("success", `Created ${v.email}`);
      reset();
      onClose();
    } catch (e) {
      setServerError(errorText(e));
    }
  };
  const field = "mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5";
  return (
    <Dialog open={open} title="Add user" onClose={onClose}>
      <form onSubmit={handleSubmit(submit)} noValidate className="space-y-3">
        <label className="block text-sm">
          Full name
          <input className={field} {...register("full_name")} />
          {errors.full_name && (
            <span className="text-red-700">{errors.full_name.message}</span>
          )}
        </label>
        <label className="block text-sm">
          Email
          <input type="email" className={field} {...register("email")} />
          {errors.email && (
            <span className="text-red-700">{errors.email.message}</span>
          )}
        </label>
        <label className="block text-sm">
          Role
          <select className={field} {...register("role")}>
            <option value="">Select…</option>
            {roles.map((r) => (
              <option key={r.id} value={r.name}>
                {r.label}
              </option>
            ))}
          </select>
          {errors.role && (
            <span className="text-red-700">{errors.role.message}</span>
          )}
        </label>
        <label className="block text-sm">
          Initial password
          <input
            type="password"
            autoComplete="new-password"
            className={field}
            {...register("password")}
          />
          {errors.password && (
            <span className="text-red-700">{errors.password.message}</span>
          )}
        </label>
        {serverError && (
          <p role="alert" className="text-sm text-red-700">
            {serverError}
          </p>
        )}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            Create
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

function ResetPasswordDialog({
  user,
  onClose,
}: {
  user: User | null;
  onClose: () => void;
}) {
  const toast = useToast();
  const [pw, setPw] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const submit = async () => {
    if (!user) return;
    setErr(null);
    try {
      await api.post(`/users/${user.id}/reset-password/`, { new_password: pw });
      toast("success", `Password reset for ${user.email}`);
      setPw("");
      onClose();
    } catch (e) {
      setErr(errorText(e));
    }
  };
  return (
    <Dialog open={user !== null} title="Reset password" onClose={onClose}>
      <label className="block text-sm">
        New password for {user?.email}
        <input
          type="password"
          autoComplete="new-password"
          value={pw}
          onChange={(e) => setPw(e.target.value)}
          className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5"
        />
      </label>
      {err && (
        <p role="alert" className="mt-2 text-sm text-red-700">
          {err}
        </p>
      )}
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <Button onClick={() => void submit()} disabled={pw.length < 12}>
          Reset
        </Button>
      </div>
    </Dialog>
  );
}

// ------------------------------------------------------------------ roles
function RolesTab() {
  const { can } = useAuth();
  const roles = useQuery({
    queryKey: ["roles"],
    queryFn: ({ signal }) => api.get<Role[]>("/roles/", signal),
  });
  const perms = useQuery({
    queryKey: ["permissions"],
    queryFn: ({ signal }) => api.get<PermissionInfo[]>("/permissions/", signal),
  });

  if (roles.isPending || perms.isPending) return <LoadingState />;
  if (roles.isError)
    return (
      <ErrorState
        message={roles.error.message}
        onRetry={() => void roles.refetch()}
      />
    );
  if (perms.isError)
    return (
      <ErrorState
        message={perms.error.message}
        onRetry={() => void perms.refetch()}
      />
    );
  return (
    <div className="space-y-4">
      {roles.data.map((r) => (
        <RoleCard
          key={r.id}
          role={r}
          all={perms.data}
          editable={can("roles.update") && r.name !== "super_admin"}
        />
      ))}
    </div>
  );
}

function RoleCard({
  role,
  all,
  editable,
}: {
  role: Role;
  all: PermissionInfo[];
  editable: boolean;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const [selected, setSelected] = useState<Set<string>>(
    new Set(role.permissions),
  );
  const dirty =
    selected.size !== role.permissions.length ||
    role.permissions.some((p) => !selected.has(p));
  const save = useMutation({
    mutationFn: () =>
      api.patch<Role>(`/roles/${role.id}/`, { permissions: [...selected] }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["roles"] });
      toast("success", `${role.label} permissions saved`);
    },
    onError: (e) => toast("error", errorText(e)),
  });
  return (
    <fieldset
      className="rounded-lg border border-slate-200 p-4"
      disabled={!editable}
    >
      <legend className="px-1 font-medium">{role.label}</legend>
      <p className="text-sm text-slate-600">{role.description}</p>
      <div className="mt-2 grid grid-cols-1 gap-1 sm:grid-cols-2">
        {all.map((p) => (
          <label key={p.codename} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={selected.has(p.codename)}
              onChange={(e) => {
                const next = new Set(selected);
                if (e.target.checked) next.add(p.codename);
                else next.delete(p.codename);
                setSelected(next);
              }}
            />
            <span className="font-mono">{p.codename}</span>
            <span className="text-slate-500">{p.description}</span>
          </label>
        ))}
      </div>
      {editable && (
        <div className="mt-3">
          <Button
            disabled={!dirty || save.isPending}
            onClick={() => save.mutate()}
          >
            Save permissions
          </Button>
        </div>
      )}
      {role.name === "super_admin" && (
        <p className="mt-2 text-xs text-slate-500">
          Super Admin always holds every permission.
        </p>
      )}
    </fieldset>
  );
}
