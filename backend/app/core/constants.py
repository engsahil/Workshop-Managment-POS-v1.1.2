"""Shared enumerations / constants for the application."""

# ---- users / roles ----
ROLE_ADMIN = "admin"
ROLE_MANAGER = "manager"
ROLE_CASHIER = "cashier"
ROLE_MECHANIC = "mechanic"

ROLES = (ROLE_ADMIN, ROLE_MANAGER, ROLE_CASHIER, ROLE_MECHANIC)

# ---- products / inventory ----
STOCK_RECEIVE = "receive"            # purchase receiving
STOCK_SALE = "sale"                # POS sale
STOCK_RETURN = "return"            # customer sale return (restock)
STOCK_ADJUST = "adjust"            # manual adjustment (+/-)
STOCK_DAMAGE = "damage"            # damaged / written off
STOCK_PURCHASE_RETURN = "purchase_return"  # returned to supplier
STOCK_JOB_CONSUME = "job_consume"  # parts consumed on a job
STOCK_JOB_RESTORE = "job_restore"  # parts restored from a job
STOCK_VOID = "void_restock"        # restock after invoice void
STOCK_TRANSFER_IN = "transfer_in"
STOCK_TRANSFER_OUT = "transfer_out"

STOCK_MOVEMENT_TYPES = (
    STOCK_RECEIVE, STOCK_SALE, STOCK_RETURN, STOCK_ADJUST, STOCK_DAMAGE,
    STOCK_PURCHASE_RETURN, STOCK_JOB_CONSUME, STOCK_JOB_RESTORE,
    STOCK_VOID, STOCK_TRANSFER_IN, STOCK_TRANSFER_OUT,
)

COSTING_WEIGHTED_AVERAGE = "weighted_average"

# ---- workshop jobs ----
JOB_STATUSES = (
    "received", "inspection", "awaiting_approval", "approved",
    "in_progress", "waiting_for_parts", "on_hold", "completed",
    "ready_for_delivery", "delivered", "cancelled",
)
JOB_TRANSITIONS = {
    "received": ("inspection", "cancelled"),
    "inspection": ("awaiting_approval", "approved", "in_progress", "received", "cancelled"),
    "awaiting_approval": ("approved", "rejected", "inspection", "cancelled"),
    "approved": ("in_progress", "waiting_for_parts", "on_hold", "cancelled"),
    "in_progress": ("waiting_for_parts", "on_hold", "completed", "cancelled"),
    "waiting_for_parts": ("in_progress", "on_hold", "cancelled"),
    "on_hold": ("in_progress", "waiting_for_parts", "cancelled"),
    "completed": ("ready_for_delivery", "delivered", "in_progress"),
    "ready_for_delivery": ("delivered", "in_progress"),
    "delivered": (),
    "cancelled": (),
    # internal marker used when an estimate is rejected back to inspection
    "rejected": ("inspection", "awaiting_approval", "cancelled"),
}
JOB_PRIORITIES = ("low", "normal", "high", "urgent")
JOB_APPROVALS = ("not_required", "pending", "approved", "rejected")

VEHICLE_TYPES = ("motorcycle", "car", "other")
FUEL_TYPES = ("petrol", "diesel", "cng", "electric", "hybrid", "unknown")

# ---- invoices / payments ----
INVOICE_STATUSES = ("paid", "partial", "credit", "void", "returned")
PAYMENT_METHODS = ("cash", "card", "bank_transfer", "jazzcash", "easypaisa", "other")
PAYMENT_METHOD_LABELS = {
    "cash": "Cash", "card": "Card", "bank_transfer": "Bank Transfer",
    "jazzcash": "JazzCash", "easypaisa": "Easypaisa", "other": "Other",
}
PAYMENT_KINDS = ("sale_payment", "refund", "advance", "repayment", "reversal")

# ---- returns ----
RETURN_REASONS = (
    "defective", "wrong_item", "not_as_described", "changed_mind",
    "warranty", "other",
)
RETURN_STATUSES = ("pending", "approved", "rejected")
RESTOCK_CHOICES = ("restock", "damaged", "discard")

# ---- expenses ----
DEFAULT_EXPENSE_CATEGORIES = (
    "Rent", "Electricity", "Salaries", "Tools & Equipment", "Utilities",
    "Maintenance", "Transport", "Miscellaneous",
)

# ---- warranty claims ----
CLAIM_STATUSES = ("open", "under_review", "approved", "rejected", "resolved", "closed")

# ---- shifts ----
SHIFT_STATUSES = ("open", "closed")
CASH_MOVEMENT_TYPES = ("addition", "withdrawal")

# ---- misc ----
YES = "yes"
NO = "no"


def label_of(mapping, key, default="—"):
    return mapping.get(key, default)
