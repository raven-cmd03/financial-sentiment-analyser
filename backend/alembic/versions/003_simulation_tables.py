"""Add simulation tables (runs, agents, trades, snapshots)

Revision ID: 003
Revises: 002
Create Date: 2026-04-22 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "simulation_runs",
        sa.Column("run_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("start_date", sa.Date()),
        sa.Column("end_date", sa.Date()),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("universe", sa.JSON(), server_default="[]"),
        sa.Column("config", sa.JSON(), server_default="{}"),
        sa.Column("report_path", sa.String(500)),
        sa.Column("final_metrics", sa.JSON(), server_default="{}"),
        sa.Column("error", sa.Text()),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index(
        "ix_simulation_runs_status", "simulation_runs", ["status"]
    )

    op.create_table(
        "trader_agents",
        sa.Column("agent_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("simulation_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("profile_name", sa.String(64), nullable=False),
        sa.Column("variant", sa.String(16), nullable=False),
        sa.Column("starting_cash", sa.Numeric(14, 4), nullable=False),
        sa.Column("final_cash", sa.Numeric(14, 4)),
        sa.Column("final_equity", sa.Numeric(14, 4)),
        sa.Column("final_return_pct", sa.Numeric(10, 4)),
        sa.Column("sharpe", sa.Numeric(10, 4)),
        sa.Column("max_drawdown", sa.Numeric(10, 4)),
        sa.Column("trade_count", sa.Integer(), server_default="0"),
        sa.Column("system_prompt", sa.Text()),
        sa.PrimaryKeyConstraint("agent_id"),
        sa.UniqueConstraint(
            "run_id",
            "profile_name",
            "variant",
            name="uq_trader_agents_run_profile_variant",
        ),
    )
    op.create_index("ix_trader_agents_run_id", "trader_agents", ["run_id"])

    op.create_table(
        "simulation_trades",
        sa.Column("trade_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "agent_id",
            sa.Integer(),
            sa.ForeignKey("trader_agents.agent_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("shares", sa.Numeric(18, 6), nullable=False),
        sa.Column("price", sa.Numeric(12, 4), nullable=False),
        sa.Column("cash_after", sa.Numeric(14, 4), nullable=False),
        sa.Column("equity_after", sa.Numeric(14, 4), nullable=False),
        sa.Column("reasoning", sa.Text()),
        sa.PrimaryKeyConstraint("trade_id"),
    )
    op.create_index("ix_simulation_trades_agent_id", "simulation_trades", ["agent_id"])
    op.create_index("ix_simulation_trades_date", "simulation_trades", ["date"])
    op.create_index("ix_simulation_trades_ticker", "simulation_trades", ["ticker"])

    op.create_table(
        "agent_daily_snapshots",
        sa.Column(
            "agent_id",
            sa.Integer(),
            sa.ForeignKey("trader_agents.agent_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("cash", sa.Numeric(14, 4), nullable=False),
        sa.Column("holdings", sa.JSON(), server_default="{}"),
        sa.Column("total_equity", sa.Numeric(14, 4), nullable=False),
        sa.PrimaryKeyConstraint("agent_id", "date"),
    )


def downgrade() -> None:
    op.drop_table("agent_daily_snapshots")
    op.drop_index("ix_simulation_trades_ticker", table_name="simulation_trades")
    op.drop_index("ix_simulation_trades_date", table_name="simulation_trades")
    op.drop_index("ix_simulation_trades_agent_id", table_name="simulation_trades")
    op.drop_table("simulation_trades")
    op.drop_index("ix_trader_agents_run_id", table_name="trader_agents")
    op.drop_table("trader_agents")
    op.drop_index("ix_simulation_runs_status", table_name="simulation_runs")
    op.drop_table("simulation_runs")
