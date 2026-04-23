"""SQLAlchemy models for the backtest trader-agent simulation subsystem.

Every simulation run produces 2N trader-agents: each declared profile is
instantiated twice, once as ``treatment`` (sees the full sentiment tool
output) and once as ``control`` (price-only baseline). The pair is the
unit of head-to-head analysis.
"""
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Date,
    Numeric,
    JSON,
    ForeignKey,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    run_id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    start_date = Column(Date)
    end_date = Column(Date)
    # pending / running / completed / failed
    status = Column(String(20), default="pending", nullable=False, index=True)
    # Tickers included in the run's universe (list[str]) plus anything else
    # worth pinning — commission/slippage, Groq model, profile list etc.
    universe = Column(JSON, default=list)
    config = Column(JSON, default=dict)
    report_path = Column(String(500))
    final_metrics = Column(JSON, default=dict)
    error = Column(Text)

    agents = relationship(
        "TraderAgent",
        back_populates="run",
        cascade="all, delete-orphan",
    )


class TraderAgent(Base):
    __tablename__ = "trader_agents"

    agent_id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(
        Integer,
        ForeignKey("simulation_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    profile_name = Column(String(64), nullable=False)
    # "treatment" (sees sentiment/news) or "control" (price-only).
    variant = Column(String(16), nullable=False)
    starting_cash = Column(Numeric(14, 4), nullable=False)
    final_cash = Column(Numeric(14, 4))
    final_equity = Column(Numeric(14, 4))
    final_return_pct = Column(Numeric(10, 4))
    sharpe = Column(Numeric(10, 4))
    max_drawdown = Column(Numeric(10, 4))
    trade_count = Column(Integer, default=0)
    system_prompt = Column(Text)

    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "profile_name",
            "variant",
            name="uq_trader_agents_run_profile_variant",
        ),
    )

    run = relationship("SimulationRun", back_populates="agents")
    trades = relationship(
        "SimulationTrade",
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    snapshots = relationship(
        "AgentDailySnapshot",
        back_populates="agent",
        cascade="all, delete-orphan",
    )


class SimulationTrade(Base):
    __tablename__ = "simulation_trades"

    trade_id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(
        Integer,
        ForeignKey("trader_agents.agent_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date = Column(Date, nullable=False, index=True)
    ticker = Column(String(10), nullable=False, index=True)
    side = Column(String(4), nullable=False)  # "buy" or "sell"
    shares = Column(Numeric(18, 6), nullable=False)
    price = Column(Numeric(12, 4), nullable=False)
    cash_after = Column(Numeric(14, 4), nullable=False)
    equity_after = Column(Numeric(14, 4), nullable=False)
    reasoning = Column(Text)

    agent = relationship("TraderAgent", back_populates="trades")


class AgentDailySnapshot(Base):
    __tablename__ = "agent_daily_snapshots"

    agent_id = Column(
        Integer,
        ForeignKey("trader_agents.agent_id", ondelete="CASCADE"),
        primary_key=True,
    )
    date = Column(Date, primary_key=True)
    cash = Column(Numeric(14, 4), nullable=False)
    # {ticker: shares} — fractional shares allowed.
    holdings = Column(JSON, default=dict)
    total_equity = Column(Numeric(14, 4), nullable=False)

    agent = relationship("TraderAgent", back_populates="snapshots")
