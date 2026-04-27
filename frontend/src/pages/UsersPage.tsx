import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Mail, Pencil, Shield, Trash2, UserPlus, Users } from "lucide-react";

import {
  createUser,
  deleteUser,
  listUsers,
  updateUser,
  type UserCreatePayload,
  type UserRecord,
  type UserUpdatePayload,
} from "../api/users";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Modal } from "../components/ui/Modal";
import { Select } from "../components/ui/Select";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { usePageTitle } from "../utils/usePageTitle";

function FieldLabel({
  children,
  hint,
}: {
  children: React.ReactNode;
  hint?: React.ReactNode;
}) {
  return (
    <label className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
      {children}
      {hint ? <span className="ml-2 normal-case tracking-normal text-slate-400">{hint}</span> : null}
    </label>
  );
}

function FieldInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className="h-12 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-sky-500 focus:ring-4 focus:ring-sky-100"
    />
  );
}

interface UserFormModalProps {
  open: boolean;
  onClose: () => void;
  initial: UserRecord | null;
  onSaved: () => void;
}

function UserFormModal({ open, onClose, initial, onSaved }: UserFormModalProps) {
  const { showToast } = useToast();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("user");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initial) {
      setFullName(initial.full_name);
      setEmail(initial.email);
      setRole(initial.role === "admin" ? "admin" : "user");
      setPassword("");
    } else {
      setFullName("");
      setEmail("");
      setPassword("");
      setRole("user");
    }
    setError(null);
  }, [initial, open]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);

    try {
      if (initial) {
        const payload: UserUpdatePayload = { full_name: fullName, email, role };
        if (password) payload.password = password;
        await updateUser(initial.id, payload);
        showToast("User updated", "success");
      } else {
        const payload: UserCreatePayload = { full_name: fullName, email, password, role };
        await createUser(payload);
        showToast("User created", "success");
      }

      onSaved();
      onClose();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Failed to save user.";
      setError(msg);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={initial ? "Edit Team Member" : "Add Team Member"}>
      <form onSubmit={handleSubmit} className="space-y-6">
        <section className="rounded-[28px] border border-slate-200 bg-slate-50 px-5 py-5">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            Access profile
          </p>
          <h3 className="mt-1 text-lg font-semibold text-slate-950">
            {initial ? "Update user permissions and credentials" : "Create a new workspace user"}
          </h3>
          <p className="mt-2 text-sm text-slate-500">
            Admins can manage users and workspace settings. Users can use the data and collection tools.
          </p>
        </section>

        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <FieldLabel>Full Name</FieldLabel>
            <FieldInput value={fullName} onChange={(e) => setFullName(e.target.value)} required autoFocus />
          </div>

          <div>
            <Select label="Role" value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </Select>
          </div>

          <div className="md:col-span-2">
            <FieldLabel>Email</FieldLabel>
            <FieldInput
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="name@company.com"
            />
          </div>

          <div className="md:col-span-2">
            <FieldLabel hint={initial ? "Leave blank to keep the current password" : undefined}>
              Password
            </FieldLabel>
            <FieldInput
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required={!initial}
              minLength={12}
              placeholder={initial ? "Enter a new password only if needed" : "At least 12 characters"}
            />
            <p className="mt-2 text-xs text-slate-500">Use at least 12 characters.</p>
          </div>
        </div>

        {error ? (
          <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <div className="flex flex-col-reverse justify-between gap-3 border-t border-slate-200 pt-5 sm:flex-row sm:items-center">
          <p className="text-xs text-slate-500">Changes apply immediately after saving.</p>
          <div className="flex gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" loading={saving}>
              {initial ? "Save Changes" : "Create User"}
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  );
}

function initials(name: string) {
  return name
    .split(" ")
    .map((part) => part[0] ?? "")
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

export function UsersPage() {
  usePageTitle("User Management");
  const { user: currentUser } = useAuth();
  const navigate = useNavigate();
  const { showToast } = useToast();

  const [users, setUsers] = useState<UserRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<UserRecord | null>(null);
  const [confirmUser, setConfirmUser] = useState<UserRecord | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (currentUser && currentUser.role !== "admin") {
      navigate("/");
    }
  }, [currentUser, navigate]);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    try {
      setUsers(await listUsers());
    } catch {
      setLoadError("Failed to load users.");
      showToast("Failed to load users", "error");
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    void load();
  }, [load]);

  function openAdd() {
    setEditing(null);
    setModalOpen(true);
  }

  function openEdit(user: UserRecord) {
    setEditing(user);
    setModalOpen(true);
  }

  async function handleDeleteConfirm() {
    if (!confirmUser) return;
    setDeleting(true);

    try {
      await deleteUser(confirmUser.id);
      setUsers((prev) => prev.filter((item) => item.id !== confirmUser.id));
      showToast("User deleted", "success");
    } catch {
      showToast("Failed to delete user", "error");
    } finally {
      setDeleting(false);
      setConfirmUser(null);
    }
  }

  const counts = useMemo(() => {
    const adminCount = users.filter((user) => user.role === "admin").length;
    return {
      total: users.length,
      adminCount,
      userCount: Math.max(users.length - adminCount, 0),
    };
  }, [users]);

  return (
    <div className="space-y-6">
      <section className="rounded-[30px] border border-slate-200 bg-white px-6 py-5 shadow-[0_18px_50px_-38px_rgba(15,23,42,0.45)]">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
              Workspace
            </p>
            <h1 className="mt-1 text-3xl font-bold text-slate-950">User Management</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
              Manage who can access the tracker and which users can administer the workspace.
            </p>
          </div>

          <Button onClick={openAdd}>
            <UserPlus className="h-4 w-4" />
            Add User
          </Button>
        </div>

        <div className="mt-6 grid gap-3 md:grid-cols-3">
          <SummaryCard label="Total users" value={counts.total} />
          <SummaryCard label="Admins" value={counts.adminCount} />
          <SummaryCard label="Users" value={counts.userCount} />
        </div>
      </section>

      {loadError ? (
        <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {loadError}
        </div>
      ) : null}

      <Card className="overflow-hidden p-0">
        <div className="border-b border-slate-200 px-6 py-4">
          <h2 className="text-[15px] font-semibold text-slate-950">Workspace Members</h2>
          <p className="mt-1 text-sm text-slate-500">Current access and role assignments.</p>
        </div>

        {loading ? (
          <div className="px-6 py-16 text-center text-sm text-slate-400">Loading users...</div>
        ) : users.length === 0 ? (
          <div className="px-6 py-16 text-center">
            <Users className="mx-auto h-10 w-10 text-slate-300" />
            <p className="mt-4 text-sm font-medium text-slate-700">No users added yet</p>
            <p className="mt-2 text-sm text-slate-500">Create a user to start assigning workspace access.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-[11px] font-semibold uppercase tracking-[0.05em] text-slate-500">
                  {["Full Name", "Email", "Role", "Created", "Actions"].map((heading) => (
                    <th key={heading} className="px-5 py-3">
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {users.map((user) => {
                  const isCurrent = user.id === currentUser?.id;
                  const isAdmin = user.role === "admin";

                  return (
                    <tr key={user.id} className="border-b border-slate-100 transition hover:bg-slate-50">
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-3">
                          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-50 text-xs font-bold text-brand-700">
                            {initials(user.full_name)}
                          </div>
                          <div className="font-medium text-slate-900">
                            {user.full_name}
                            {isCurrent ? (
                              <span className="ml-2 rounded-full border border-sky-200 bg-sky-50 px-2 py-0.5 text-[11px] font-medium text-sky-700">
                                You
                              </span>
                            ) : null}
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-4 text-sm text-slate-600">{user.email}</td>
                      <td className="px-5 py-4">
                        <span
                          className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${
                            isAdmin
                              ? "border border-violet-200 bg-violet-50 text-violet-700"
                              : "border border-slate-200 bg-slate-50 text-slate-600"
                          }`}
                        >
                          {isAdmin ? <Shield className="h-3.5 w-3.5" /> : <Mail className="h-3.5 w-3.5" />}
                          {isAdmin ? "Admin" : "User"}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-sm text-slate-500">
                        {new Date(user.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-2">
                          <Button variant="secondary" size="sm" onClick={() => openEdit(user)}>
                            <Pencil className="h-4 w-4" />
                            Edit
                          </Button>
                          {!isCurrent ? (
                            <Button variant="danger" size="sm" onClick={() => setConfirmUser(user)}>
                              <Trash2 className="h-4 w-4" />
                              Delete
                            </Button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <UserFormModal open={modalOpen} onClose={() => setModalOpen(false)} initial={editing} onSaved={load} />

      {confirmUser ? (
        <Modal open={true} onClose={() => setConfirmUser(null)} title="Delete User">
          <div className="space-y-6">
            <section className="rounded-[28px] border border-red-200 bg-red-50 px-5 py-5">
              <p className="text-lg font-semibold text-slate-950">Remove {confirmUser.full_name}?</p>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                This will permanently revoke access for{" "}
                <span className="font-medium text-slate-900">{confirmUser.email}</span>.
              </p>
            </section>

            <div className="flex justify-end gap-3">
              <Button variant="secondary" onClick={() => setConfirmUser(null)}>
                Cancel
              </Button>
              <Button variant="danger" onClick={handleDeleteConfirm} loading={deleting}>
                Delete User
              </Button>
            </div>
          </div>
        </Modal>
      ) : null}
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-2 text-3xl font-semibold text-slate-950">{value}</p>
    </div>
  );
}
