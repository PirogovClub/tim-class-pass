"""Canonical lexicon: maps known Russian trading terms to stable canonical slugs.

Used by canonicalization.py to generate language-neutral IDs from Russian concept names.
If a term is not found, canonicalization falls back to deterministic slugification.
"""

from __future__ import annotations

CONCEPT_ALIASES: dict[str, str] = {
    # Core level concepts
    "уровень": "level",
    "уровни": "level",
    "зона": "zone",
    "зоны": "zone",
    "поддержка": "support",
    "сопротивление": "resistance",
    "зеркальный уровень": "mirror_level",
    "сильный уровень": "strong_level",
    "исторический уровень": "historical_level",
    "лимитный уровень": "limit_level",
    "уровень лимитного игрока": "limit_player_level",
    # Breakout / false breakout
    "пробой": "breakout",
    "пробой уровня": "level_breakout",
    "ложный пробой": "false_breakout",
    "подтверждённый пробой": "confirmed_breakout",
    # Trend / reversal
    "тренд": "trend",
    "разворот": "reversal",
    "ретест": "retest",
    "консолидация": "consolidation",
    "накопление": "accumulation",
    "распределение": "distribution",
    # Entry / exit
    "вход в сделку": "trade_entry",
    "выход из сделки": "trade_exit",
    "точка входа": "entry_point",
    "сигнал входа": "entry_signal",
    # Risk management
    "стоп-лосс": "stop_loss",
    "стоп лосс": "stop_loss",
    "тейк-профит": "take_profit",
    "тейк профит": "take_profit",
    "управление риском": "risk_management",
    "риск": "risk",
    "соотношение риск-прибыль": "risk_reward_ratio",
    # Volume / bars
    "объем": "volume",
    "объёмы": "volume",
    "паранормальный бар": "paranormal_bar",
    "бар": "bar",
    "свеча": "candle",
    # Market participants
    "крупный игрок": "large_player",
    "лимитный игрок": "limit_player",
    # Other common terms
    "закрепление": "acceptance",
    "закругление": "rounding",
    "проторговка": "protrogovka",
    "протаргивание": "protrogovka",
    "подтверждение": "confirmation",
    "подтверждение уровня": "level_confirmation",
    "торговая ситуация": "trading_situation",
    "защита уровней": "level_defense",
    "бсу": "bsu",
    "твх": "tvh",
    "недоход бара": "bar_undershoot",
    # English terms already seen in data (normalize casing)
    "level": "level",
    "levels": "level",
    "zone": "zone",
    "false breakout": "false_breakout",
    "breakout": "breakout",
    "breakout trading": "breakout_trading",
    "reversal": "reversal",
    "reversal trading": "reversal_trading",
    "retest": "retest",
    "support and resistance": "support_and_resistance",
    "mirror level": "mirror_level",
    "strong level": "strong_level",
    "risk management": "risk_management",
    "stop loss": "stop_loss",
    "stop-loss": "stop_loss",
    "take profit": "take_profit",
    "trade entry": "trade_entry",
    "trade execution": "trade_execution",
    "trade management": "trade_management",
    "entry strategy": "entry_strategy",
    "exit strategy": "exit_strategy",
    "trading strategy": "trading_strategy",
    "volume analysis": "volume_analysis",
    "price action": "price_action",
    "paranormal bar": "paranormal_bar",
    "accumulation": "accumulation",
    "distribution": "distribution",
    "consolidation": "consolidation",
    "confirmation": "confirmation",
    "trend continuation": "trend_continuation",
    "trend reversal": "trend_reversal",
    "profit target": "profit_target",
    "position management": "position_management",
    "order placement": "order_placement",
    "chart analysis": "chart_analysis",
    "atr": "atr",
    "ipo": "ipo",
    "bpu": "bpu",
}


def lookup_canonical(text: str) -> str | None:
    """Return canonical slug if text (lowercased, trimmed) matches registry, else None."""
    key = text.strip().lower()
    return CONCEPT_ALIASES.get(key)
