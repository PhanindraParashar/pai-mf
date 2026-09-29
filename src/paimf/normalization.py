from __future__ import annotations

import numpy as np
import pandas as pd


class ScoreNormalizer:
    @staticmethod
    def _online_percentile(
        values: pd.Series,
        min_periods: int,
    ) -> pd.Series:
        """Expanding percentile with current observation included and no lookahead."""
        numbers = values.to_numpy(dtype=float)
        valid = np.isfinite(numbers)
        coordinates = np.unique(numbers[valid])
        tree = np.zeros(len(coordinates) + 1, dtype=np.int64)
        result = np.full(len(numbers), np.nan)
        count = 0

        for row, value in enumerate(numbers):
            if not valid[row]:
                continue
            position = int(np.searchsorted(coordinates, value)) + 1
            update = position
            while update < len(tree):
                tree[update] += 1
                update += update & -update
            count += 1
            if count >= min_periods:
                rank = 0
                query = position
                while query:
                    rank += tree[query]
                    query -= query & -query
                result[row] = rank / count

        return pd.Series(result, index=values.index)

    @classmethod
    def historical(
        cls,
        df: pd.DataFrame,
        columns: list[str],
        group_cols: list[str],
        lower_is_better: set[str] | None = None,
        min_periods: int = 12,
    ) -> pd.DataFrame:
        lower_is_better = lower_is_better or set()
        pieces = []

        ordered = df.sort_values([*group_cols, "date"])

        for _, group in ordered.groupby(
            group_cols,
            sort=False,
            observed=True,
        ):
            group = group.copy()

            for col in columns:
                score = cls._online_percentile(
                    group[col],
                    min_periods,
                )

                if col in lower_is_better:
                    score = 1.0 - score

                group[f"{col}_score"] = score

            pieces.append(group)

        if not pieces:
            out = ordered.copy()
            for col in columns:
                out[f"{col}_score"] = np.nan
            return out
        return pd.concat(
            pieces,
            ignore_index=True,
        )

    @staticmethod
    def cross_sectional(
        df: pd.DataFrame,
        columns: list[str],
        group_cols: list[str],
        lower_is_better: set[str] | None = None,
    ) -> pd.DataFrame:
        lower_is_better = lower_is_better or set()

        out = df.copy()

        for col in columns:
            score = out.groupby(
                group_cols,
                observed=True,
                dropna=False,
            )[col].rank(
                pct=True,
                method="average",
            )

            if col in lower_is_better:
                score = 1.0 - score

            out[f"{col}_score"] = score

        return out
