"""
Analytics service: uses Pandas to compute aggregated sales reports and
export large datasets as streaming CSV.
"""

import io
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import AsyncGenerator

import pandas as pd
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.schemas.schemas import SalesReport

logger = structlog.get_logger(__name__)


class AnalyticsService:
    # ── Sales Report ──────────────────────────────────────────────────────────

    async def sales_report(
        self,
        db: AsyncSession,
        start_date: date,
        end_date: date,
    ) -> SalesReport:
        """Aggregate order + product data into a summary report using Pandas."""
        sql = text("""
            SELECT
                o.id            AS order_id,
                o.status,
                o.total_amount,
                o.created_at    AS order_date,
                oi.product_id,
                p.name          AS product_name,
                oi.quantity,
                oi.unit_price
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.id
            JOIN products p     ON p.id = oi.product_id
            WHERE o.created_at BETWEEN :start AND :end
              AND o.status != 'cancelled'
        """)

        result = await db.execute(sql, {"start": start_date, "end": end_date})
        rows = result.mappings().all()

        if not rows:
            return SalesReport(
                period=f"{start_date} to {end_date}",
                total_orders=0,
                total_revenue=Decimal("0.00"),
                avg_order_value=Decimal("0.00"),
                top_products=[],
            )

        df = pd.DataFrame(rows)
        df["order_date"] = pd.to_datetime(df["order_date"])
        df["total_amount"] = pd.to_numeric(df["total_amount"])
        df["unit_price"] = pd.to_numeric(df["unit_price"])
        df["line_total"] = df["quantity"] * df["unit_price"]

        unique_orders = df.drop_duplicates("order_id")
        total_orders = unique_orders["order_id"].nunique()
        total_revenue = Decimal(str(round(df["line_total"].sum(), 2)))
        avg_order_value = Decimal(str(round(unique_orders["total_amount"].mean(), 2)))

        top_products = (
            df.groupby(["product_id", "product_name"])
            .agg(units_sold=("quantity", "sum"), revenue=("line_total", "sum"))
            .reset_index()
            .sort_values("revenue", ascending=False)
            .head(10)
            .assign(revenue=lambda x: x["revenue"].round(2))
            .rename(columns={"product_id": "id", "product_name": "name"})
            .to_dict(orient="records")
        )

        logger.info(
            "sales_report_generated",
            start=str(start_date),
            end=str(end_date),
            total_orders=total_orders,
            total_revenue=str(total_revenue),
        )

        return SalesReport(
            period=f"{start_date} to {end_date}",
            total_orders=total_orders,
            total_revenue=total_revenue,
            avg_order_value=avg_order_value,
            top_products=top_products,
        )

    # ── Streaming CSV Export ──────────────────────────────────────────────────

    async def export_orders_csv(
        self,
        db: AsyncSession,
        start_date: date,
        end_date: date,
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream orders as CSV in configurable chunks — safe for large datasets
        without loading everything into memory at once.
        """
        sql = text("""
            SELECT
                o.id, o.status, o.total_amount, o.created_at,
                u.email AS user_email,
                p.name  AS product_name, p.sku,
                oi.quantity, oi.unit_price
            FROM orders o
            JOIN users u        ON u.id = o.user_id
            JOIN order_items oi ON oi.order_id = o.id
            JOIN products p     ON p.id = oi.product_id
            WHERE o.created_at BETWEEN :start AND :end
            ORDER BY o.created_at DESC
            LIMIT :limit
        """)

        result = await db.execute(
            sql,
            {"start": start_date, "end": end_date, "limit": settings.DATA_EXPORT_MAX_ROWS},
        )
        rows = result.mappings().all()

        if not rows:
            yield b"No data available for the selected date range\n"
            return

        df = pd.DataFrame(rows)
        chunk_size = settings.DATA_EXPORT_CHUNK_SIZE

        for i, chunk_start in enumerate(range(0, len(df), chunk_size)):
            chunk = df.iloc[chunk_start : chunk_start + chunk_size]
            buf = io.StringIO()
            chunk.to_csv(buf, index=False, header=(i == 0))
            yield buf.getvalue().encode("utf-8")

    # ── Revenue Trend ─────────────────────────────────────────────────────────

    async def revenue_trend(
        self,
        db: AsyncSession,
        days: int = 30,
    ) -> list[dict]:
        """Daily revenue for the last N days."""
        start = datetime.now(timezone.utc) - timedelta(days=days)
        sql = text("""
            SELECT
                DATE(created_at) AS day,
                COUNT(*)         AS orders,
                SUM(total_amount) AS revenue
            FROM orders
            WHERE created_at >= :start AND status != 'cancelled'
            GROUP BY DATE(created_at)
            ORDER BY day
        """)

        result = await db.execute(sql, {"start": start})
        rows = result.mappings().all()

        if not rows:
            return []

        df = pd.DataFrame(rows)
        df["revenue"] = df["revenue"].astype(float).round(2)
        df["day"] = df["day"].astype(str)
        return df.to_dict(orient="records")


analytics_service = AnalyticsService()
