"""
Python port of AgeGradeCalculator.swift.

Usage:
    from age_grade import AgeGradeCalculator
    ag = AgeGradeCalculator()
    result = ag.result(distance_m=5000, time_sec=1200, age=45, gender='M')
    print(result.percentage)   # e.g. 72.3
"""

import os
import math
from dataclasses import dataclass
from typing import Optional

_FILENAME_TO_METERS = {
    "AgeGrade.1mi":   1609.344,
    "AgeGrade.4mi":   6437.376,
    "AgeGrade.5mi":   8046.72,
    "AgeGrade.5k":    5000.0,
    "AgeGrade.6k":    6000.0,
    "AgeGrade.8k":    8000.0,
    "AgeGrade.10k":  10000.0,
    "AgeGrade.10mi": 16093.44,
    "AgeGrade.12k":  12000.0,
    "AgeGrade.15k":  15000.0,
    "AgeGrade.20k":  20000.0,
    "AgeGrade.25k":  25000.0,
    "AgeGrade.30k":  30000.0,
    "AgeGrade.42k":  42195.0,
    "AgeGrade.50k":  50000.0,
    "AgeGrade.50mi": 80467.2,
    "AgeGrade.100k": 100000.0,
    "AgeGrade.100mi":160934.4,
    "AgeGrade.150k": 150000.0,
    "AgeGrade.200k": 200000.0,
    "AgeGrade.hm":   21097.5,
}


def _parse_time(text: str) -> Optional[float]:
    parts = text.split(":")
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return None
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    return None


@dataclass
class AgeGradeResult:
    factor: float              # age factor (<1 = performance decline with age)
    age_graded_mark_sec: float # open-age equivalent time
    percentage: float          # % of age standard (higher = better)


class AgeGradeCalculator:
    def __init__(self, runscore_dir: Optional[str] = None):
        if runscore_dir is None:
            runscore_dir = os.path.join(os.path.dirname(__file__), "age_grade_calc", "RunScore")
        self._tables: dict[float, dict] = {}
        self._load(runscore_dir)

    def _load(self, directory: str):
        for filename, meters in _FILENAME_TO_METERS.items():
            path = os.path.join(directory, filename)
            if not os.path.exists(path):
                continue
            table = self._parse_table(path)
            if table:
                self._tables[meters] = table

    def _parse_table(self, path: str) -> Optional[dict]:
        male_wr = None
        female_wr = None
        male_factors: dict[int, float] = {}
        female_factors: dict[int, float] = {}

        with open(path, encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 2:
                    continue
                gender_token = parts[0]
                if len(parts) == 2:
                    # World record line: "M 0:12:49"
                    secs = _parse_time(parts[1])
                    if secs is None:
                        continue
                    if gender_token == "M":
                        male_wr = secs
                    elif gender_token == "F":
                        female_wr = secs
                elif len(parts) == 3:
                    # Age factor line: "M 50 0.8761"
                    try:
                        age = int(parts[1])
                        factor = float(parts[2])
                    except ValueError:
                        continue
                    if gender_token == "M":
                        male_factors[age] = factor
                    elif gender_token == "F":
                        female_factors[age] = factor

        if male_wr is None or female_wr is None:
            return None
        if not male_factors or not female_factors:
            return None

        return {
            "male_wr": male_wr,
            "female_wr": female_wr,
            "male_factors": male_factors,
            "female_factors": female_factors,
        }

    def _nearest_table(self, meters: float, tolerance: float = 0.5) -> Optional[dict]:
        if meters in self._tables:
            return self._tables[meters]
        for key, table in self._tables.items():
            if abs(key - meters) < tolerance:
                return table
        return None

    def result(self, distance_m: float, time_sec: float, age: int, gender: str) -> Optional[AgeGradeResult]:
        """
        gender: 'M' or 'F'
        Returns None if the distance or age is not in the tables.
        """
        table = self._nearest_table(distance_m)
        if table is None:
            return None
        if gender == "M":
            wr = table["male_wr"]
            factors = table["male_factors"]
        elif gender == "F":
            wr = table["female_wr"]
            factors = table["female_factors"]
        else:
            return None

        factor = factors.get(age)
        if factor is None or factor <= 0 or time_sec <= 0:
            return None

        age_standard = wr / factor
        age_graded_mark = time_sec * factor
        percentage = (age_standard / time_sec) * 100
        return AgeGradeResult(factor=factor, age_graded_mark_sec=age_graded_mark, percentage=percentage)
