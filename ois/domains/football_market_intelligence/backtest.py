"""Walk-forward market backtesting primitives."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .engine import MarketSignal


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    starting_bankroll: float = 100.0
    kelly_fraction: float = 0.25
    max_stake_fraction: float = 0.05
    min_stake: float = 0.0

    def __post_init__(self) -> None:
        if self.starting_bankroll <= 0:
            raise ValueError("starting_bankroll must be positive")
        if not 0 < self.kelly_fraction <= 1:
            raise ValueError("kelly_fraction must be in (0, 1]")
        if not 0 < self.max_stake_fraction <= 1:
            raise ValueError("max_stake_fraction must be in (0, 1]")
        if self.min_stake < 0:
            raise ValueError("min_stake cannot be negative")


@dataclass(frozen=True, slots=True)
class BacktestBet:
    match_id: str
    selection: str
    odds: float
    model_probability: float
    stake: float
    won: bool
    pnl: float
    settled_at: datetime


@dataclass(frozen=True, slots=True)
class BacktestResult:
    starting_bankroll: float
    ending_bankroll: float
    bets: tuple[BacktestBet, ...]

    @property
    def net_pnl(self) -> float:
        return self.ending_bankroll - self.starting_bankroll

    @property
    def roi(self) -> float:
        total_staked = sum(bet.stake for bet in self.bets)
        return self.net_pnl / total_staked if total_staked else 0.0

    @property
    def hit_rate(self) -> float:
        return sum(1 for bet in self.bets if bet.won) / len(self.bets) if self.bets else 0.0


def run_backtest(
    signals: list[MarketSignal],
    outcomes: dict[tuple[str, str], bool],
    settled_at: dict[str, datetime],
    config: BacktestConfig | None = None,
) -> BacktestResult:
    """Replay signals chronologically without using future observations."""
    cfg = config or BacktestConfig()
    bankroll = cfg.starting_bankroll
    bets: list[BacktestBet] = []
    ordered = sorted(signals, key=lambda s: (s.prediction_timestamp, s.match_id, s.selection))
    for signal in ordered:
        settlement_time = settled_at.get(signal.match_id)
        if settlement_time is None or signal.prediction_timestamp >= settlement_time:
            continue
        won = outcomes.get((signal.match_id, signal.selection))
        if won is None:
            continue
        stake = min(
            bankroll * cfg.max_stake_fraction,
            bankroll * signal.kelly_fraction * cfg.kelly_fraction,
        )
        if stake < cfg.min_stake or stake <= 0:
            continue
        pnl = stake * (signal.odds - 1.0) if won else -stake
        bankroll += pnl
        bets.append(
            BacktestBet(
                match_id=signal.match_id,
                selection=signal.selection,
                odds=signal.odds,
                model_probability=signal.model_probability,
                stake=stake,
                won=won,
                pnl=pnl,
                settled_at=settlement_time,
            )
        )
    return BacktestResult(cfg.starting_bankroll, bankroll, tuple(bets))
