"""Database tables for the Auto Workshop POS."""
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Float, ForeignKey, Index, Integer,
    Numeric, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from ..core.security import utcnow


def _now() -> datetime:
    return utcnow()


def _uid() -> str:
    return uuid.uuid4().hex


# ---------------------------------------------------------------- users
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(24), nullable=False, default="cashier")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


# ---------------------------------------------------------------- customers
class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(24), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    alt_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    cnic: Mapped[str | None] = mapped_column(String(30), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    vehicles = relationship("Vehicle", back_populates="customer", cascade="all, delete-orphan")


# ---------------------------------------------------------------- vehicles
class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    vehicle_type: Mapped[str] = mapped_column(String(24), default="motorcycle")
    registration_no: Mapped[str | None] = mapped_column(String(40), index=True)
    make: Mapped[str | None] = mapped_column(String(60))
    model: Mapped[str | None] = mapped_column(String(80))
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    color: Mapped[str | None] = mapped_column(String(40))
    engine_no: Mapped[str | None] = mapped_column(String(60))
    chassis_no: Mapped[str | None] = mapped_column(String(60))
    odometer: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fuel_type: Mapped[str | None] = mapped_column(String(24))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    customer = relationship("Customer", back_populates="vehicles")
    __table_args__ = (Index("ix_vehicle_reg_lower", "registration_no"),)


# ---------------------------------------------------------------- catalog
class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Brand(Base):
    __tablename__ = "brands"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    sku: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    barcode: Mapped[str | None] = mapped_column(String(80), unique=True, index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    brand_id: Mapped[int | None] = mapped_column(ForeignKey("brands.id", ondelete="SET NULL"), nullable=True)
    compatibility: Mapped[str | None] = mapped_column(String(200))      # model / fitment notes
    purchase_cost_paisa: Mapped[int] = mapped_column(BigInteger, default=0)   # weighted-average cost is on StockMovement history
    selling_price_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    quantity_on_hand: Mapped[int] = mapped_column(Integer, default=0)  # cache; always reconciled with movements
    min_stock: Mapped[int] = mapped_column(Integer, default=0)
    unit: Mapped[str] = mapped_column(String(24), default="pcs")
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_service: Mapped[bool] = mapped_column(Boolean, default=False)   # never a stock item
    warranty_days: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    category = relationship("Category")
    brand = relationship("Brand")
    supplier = relationship("Supplier")


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    movement_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    quantity_delta: Mapped[int] = mapped_column(Integer, nullable=False)     # signed
    quantity_after: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost_paisa: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reference_type: Mapped[str | None] = mapped_column(String(40))           # sale / purchase / job / adjustment ...
    reference_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reference_number: Mapped[str | None] = mapped_column(String(48))
    notes: Mapped[str | None] = mapped_column(String(300))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)

    product = relationship("Product")


# ---------------------------------------------------------------- suppliers / purchases
class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    contact_person: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(32), index=True)
    alt_phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(160))
    address: Mapped[str | None] = mapped_column(String(300))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    po_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False, index=True)
    order_date: Mapped[datetime] = mapped_column(DateTime, default=_now)
    status: Mapped[str] = mapped_column(String(24), default="ordered")  # ordered | partial | received | cancelled
    subtotal_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    discount_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    total_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    paid_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    supplier = relationship("Supplier")
    items = relationship("PurchaseItem", back_populates="purchase", cascade="all, delete-orphan")


class PurchaseItem(Base):
    __tablename__ = "purchase_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    received_quantity: Mapped[int] = mapped_column(Integer, default=0)
    unit_cost_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    line_total_paisa: Mapped[int] = mapped_column(BigInteger, default=0)

    purchase = relationship("Purchase", back_populates="items")
    product = relationship("Product")


class PurchasePayment(Base):
    __tablename__ = "purchase_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False, index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    amount_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    method: Mapped[str] = mapped_column(String(24), default="cash")
    reference: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(String(300))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)


class PurchaseReturn(Base):
    __tablename__ = "purchase_returns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    return_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id"), nullable=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False, index=True)
    return_date: Mapped[datetime] = mapped_column(DateTime, default=_now)
    total_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    refund_amount_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    method: Mapped[str] = mapped_column(String(24), default="cash")
    reference: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(24), default="approved")  # pending | approved | rejected
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    items = relationship("PurchaseReturnItem", back_populates="return_", cascade="all, delete-orphan")


class PurchaseReturnItem(Base):
    __tablename__ = "purchase_return_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    return_id: Mapped[int] = mapped_column(ForeignKey("purchase_returns.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    line_total_paisa: Mapped[int] = mapped_column(BigInteger, default=0)

    return_ = relationship("PurchaseReturn", back_populates="items")
    product = relationship("Product")


# ---------------------------------------------------------------- services / staff
class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    code: Mapped[str | None] = mapped_column(String(48), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    default_charge_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=0)
    vehicle_types: Mapped[str] = mapped_column(String(60), default="motorcycle,car")  # comma list
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class Mechanic(Base):
    __tablename__ = "mechanics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(32))
    skill: Mapped[str | None] = mapped_column(String(120))       # e.g. "Engine, Electrical"
    commission_type: Mapped[str] = mapped_column(String(24), default="none")  # none | percent_per_job | fixed_per_job
    commission_value: Mapped[int] = mapped_column(BigInteger, default=0)      # percent*100 (e.g. 500 = 5%) or paisa fixed
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    hire_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


# ---------------------------------------------------------------- job cards
class JobCard(Base):
    __tablename__ = "job_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False, index=True)
    checkin_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    odometer: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reported_issue: Mapped[str | None] = mapped_column(Text)
    complaint: Mapped[str | None] = mapped_column(Text)
    inspection: Mapped[str | None] = mapped_column(Text)
    vehicle_condition: Mapped[str | None] = mapped_column(Text)
    existing_damage: Mapped[str | None] = mapped_column(Text)
    fuel_level: Mapped[str | None] = mapped_column(String(20))
    mechanic_id: Mapped[int | None] = mapped_column(ForeignKey("mechanics.id", ondelete="SET NULL"), nullable=True, index=True)
    est_labor_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    est_parts_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    est_completion_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    internal_notes: Mapped[str | None] = mapped_column(Text)
    customer_notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(28), default="received", index=True)
    approval_status: Mapped[str] = mapped_column(String(24), default="not_required", index=True)
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True)
    warranty_days: Mapped[int] = mapped_column(Integer, default=0)
    actual_labor_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    actual_parts_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    customer = relationship("Customer")
    vehicle = relationship("Vehicle")
    mechanic = relationship("Mechanic")
    services = relationship("JobService", back_populates="job", cascade="all, delete-orphan")
    parts = relationship("JobPart", back_populates="job", cascade="all, delete-orphan")
    history = relationship("JobHistory", back_populates="job", cascade="all, delete-orphan", order_by="JobHistory.id")


class JobService(Base):
    __tablename__ = "job_services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("job_cards.id", ondelete="CASCADE"), nullable=False, index=True)
    service_id: Mapped[int | None] = mapped_column(ForeignKey("services.id"), nullable=True)
    description: Mapped[str] = mapped_column(String(240), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_charge_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    discount_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    line_total_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    mechanic_id: Mapped[int | None] = mapped_column(ForeignKey("mechanics.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    job = relationship("JobCard", back_populates="services")
    service = relationship("Service")


class JobPart(Base):
    __tablename__ = "job_parts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("job_cards.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    line_total_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    stock_deducted: Mapped[bool] = mapped_column(Boolean, default=False)
    stock_movement_id: Mapped[int | None] = mapped_column(ForeignKey("stock_movements.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    job = relationship("JobCard", back_populates="parts")
    product = relationship("Product")
    stock_movement = relationship("StockMovement")


class JobHistory(Base):
    __tablename__ = "job_histories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("job_cards.id", ondelete="CASCADE"), nullable=False, index=True)
    from_status: Mapped[str | None] = mapped_column(String(28))
    to_status: Mapped[str | None] = mapped_column(String(28))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    job = relationship("JobCard", back_populates="history")


# ---------------------------------------------------------------- invoices / payments
class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("job_cards.id", ondelete="SET NULL"), nullable=True, index=True)
    subtotal_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    discount_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    tax_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    total_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    paid_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    balance_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    cost_of_goods_paisa: Mapped[int] = mapped_column(BigInteger, default=0)   # snapshot for profit calc
    status: Mapped[str] = mapped_column(String(20), default="credit", index=True)  # paid | partial | credit | void | returned
    payment_method_summary: Mapped[str | None] = mapped_column(String(300))    # JSON-ish text
    cashier_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    shift_id: Mapped[int | None] = mapped_column(ForeignKey("cash_shifts.id", ondelete="SET NULL"), nullable=True)
    is_credit: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    return_amount_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    credited_amount_paisa: Mapped[int] = mapped_column(BigInteger, default=0)  # credit-note portion of returns
    voided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    void_reason: Mapped[str | None] = mapped_column(String(300))
    voided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    customer = relationship("Customer")
    vehicle = relationship("Vehicle")
    job = relationship("JobCard", foreign_keys=[job_id])
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    item_type: Mapped[str] = mapped_column(String(16), default="product")  # product | service
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    service_id: Mapped[int | None] = mapped_column(ForeignKey("services.id"), nullable=True)
    job_part_id: Mapped[int | None] = mapped_column(ForeignKey("job_parts.id"), nullable=True)
    job_service_id: Mapped[int | None] = mapped_column(ForeignKey("job_services.id"), nullable=True)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), default=1)
    unit: Mapped[str] = mapped_column(String(24), default="pcs")
    unit_price_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    discount_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    line_total_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    unit_cost_paisa: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # snapshot for profit
    is_warranty: Mapped[bool] = mapped_column(Boolean, default=False)

    invoice = relationship("Invoice", back_populates="items")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    amount_paisa: Mapped[int] = mapped_column(BigInteger, default=0)      # signed (+ received, - refund/reversal)
    method: Mapped[str] = mapped_column(String(24), default="cash")
    kind: Mapped[str] = mapped_column(String(20), default="sale_payment")
    reference: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(String(300))
    shift_id: Mapped[int | None] = mapped_column(ForeignKey("cash_shifts.id", ondelete="SET NULL"), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)

    invoice = relationship("Invoice", back_populates="payments")


# ---------------------------------------------------------------- returns
class SaleReturn(Base):
    __tablename__ = "sale_returns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    return_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False, index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(120))
    return_date: Mapped[datetime] = mapped_column(DateTime, default=_now)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    restock_action: Mapped[str] = mapped_column(String(20), default="restock")  # restock | damaged | discard
    total_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    refund_method: Mapped[str] = mapped_column(String(24), default="cash")     # cash | card | ... | credit
    refund_amount_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    credit_amount_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    items = relationship("SaleReturnItem", back_populates="return_", cascade="all, delete-orphan")
    invoice = relationship("Invoice")


class SaleReturnItem(Base):
    __tablename__ = "sale_return_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    return_id: Mapped[int] = mapped_column(ForeignKey("sale_returns.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_item_id: Mapped[int | None] = mapped_column(ForeignKey("invoice_items.id"), nullable=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    description: Mapped[str | None] = mapped_column(String(300))
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), default=1)
    unit_price_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    line_total_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    restocked_quantity: Mapped[float] = mapped_column(Numeric(12, 3), default=0)

    return_ = relationship("SaleReturn", back_populates="items")


# ---------------------------------------------------------------- expenses
class ExpenseCategory(Base):
    __tablename__ = "expense_categories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    expense_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("expense_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    amount_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    expense_date: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
    method: Mapped[str] = mapped_column(String(24), default="cash")
    payee: Mapped[str | None] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    reference: Mapped[str | None] = mapped_column(String(120))
    attachment_path: Mapped[str | None] = mapped_column(String(300))
    shift_id: Mapped[int | None] = mapped_column(ForeignKey("cash_shifts.id", ondelete="SET NULL"), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    category = relationship("ExpenseCategory")


# ---------------------------------------------------------------- warranty claims
class WarrantyClaim(Base):
    __tablename__ = "warranty_claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    claim_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True)
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("job_cards.id"), nullable=True)
    item_type: Mapped[str] = mapped_column(String(16), default="product")   # product | service
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    service_id: Mapped[int | None] = mapped_column(ForeignKey("services.id"), nullable=True)
    purchase_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    warranty_days: Mapped[int] = mapped_column(Integer, default=0)
    claim_date: Mapped[datetime] = mapped_column(DateTime, default=_now)
    description: Mapped[str | None] = mapped_column(Text)
    inspection_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_taken: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    resolution: Mapped[str | None] = mapped_column(Text)
    cost_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    refund_amount_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


# ---------------------------------------------------------------- cashier shifts
class CashShift(Base):
    __tablename__ = "cash_shifts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
    opening_cash_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    expected_cash_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    counted_cash_paisa: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    difference_paisa: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closing_notes: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    closed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    cash_movements = relationship("CashMovement", back_populates="shift", cascade="all, delete-orphan")


class CashMovement(Base):
    __tablename__ = "cash_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shift_id: Mapped[int] = mapped_column(ForeignKey("cash_shifts.id", ondelete="CASCADE"), nullable=False, index=True)
    movement_type: Mapped[str] = mapped_column(String(16), nullable=False)  # addition | withdrawal
    amount_paisa: Mapped[int] = mapped_column(BigInteger, default=0)
    reason: Mapped[str | None] = mapped_column(String(200))
    reference: Mapped[str | None] = mapped_column(String(120))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    shift = relationship("CashShift", back_populates="cash_movements")


# ---------------------------------------------------------------- system
class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(48))
    entity_id: Mapped[str | None] = mapped_column(String(48))
    old_values: Mapped[str | None] = mapped_column(Text)
    new_values: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(40), nullable=False)   # low_stock | job_status | payment | payment_due
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(String(500))
    related_type: Mapped[str | None] = mapped_column(String(40))
    related_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
