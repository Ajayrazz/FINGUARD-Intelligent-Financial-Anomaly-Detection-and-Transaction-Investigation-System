"""Single source of truth for roles and permission codenames (docs/10).

Codenames are `resource.action`. New phases add codenames here; `seed_roles` grants defaults only for
codenames not seen before, so permissions edited by a Super Admin are never overwritten.
"""

SUPER_ADMIN = "super_admin"
FINANCIAL_ANALYST = "financial_analyst"
FRAUD_INVESTIGATOR = "fraud_investigator"
AUDITOR = "auditor"
MANAGEMENT = "management"

ROLES: dict[str, tuple[str, str]] = {
    SUPER_ADMIN: ("Super Admin", "Manage users, roles, system settings, risk parameters and models."),
    FINANCIAL_ANALYST: ("Financial Analyst", "Monitor transactions, review alerts, examine risk."),
    FRAUD_INVESTIGATOR: ("Fraud Investigator", "Investigate cases, maintain evidence, produce reports."),
    AUDITOR: ("Auditor", "Read-only access to investigation history and audit records."),
    MANAGEMENT: ("Management", "High-level analytics, risk trends and organisational reports."),
}

PERMISSIONS: dict[str, str] = {
    "users.read": "View users",
    "users.create": "Create users",
    "users.update": "Update, activate/deactivate users and reset passwords",
    "roles.read": "View roles and permissions",
    "roles.create": "Create roles",
    "roles.update": "Edit role permissions",
    "audit.read": "View audit logs",
    "datasets.read": "View datasets and import history",
    "datasets.create": "Create datasets",
    "transactions.read": "View transactions",
    "transactions.update_status": "Change a transaction's monitoring status",
    "accounts.read": "View financial accounts",
}

# Defaults for non-super-admin roles (super admin always receives every permission).
DEFAULT_ROLE_PERMISSIONS: dict[str, set[str]] = {
    FINANCIAL_ANALYST: {
        "datasets.read",
        "datasets.create",
        "transactions.read",
        "transactions.update_status",
        "accounts.read",
    },
    FRAUD_INVESTIGATOR: {"datasets.read", "transactions.read", "accounts.read"},
    AUDITOR: {
        "users.read",
        "roles.read",
        "audit.read",
        "datasets.read",
        "transactions.read",
        "accounts.read",
    },
    MANAGEMENT: set(),
}
