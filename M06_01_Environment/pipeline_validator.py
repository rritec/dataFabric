# =============================================================================
# pipeline_validator.py
# Microsoft Fabric — Single .py Custom Library  |  Version 3.0.0
#
# Purpose  : Validate data pipeline — Lakehouse → Warehouse reconciliation
#
# IMPORTANT — Connector usage rules (learned from real Fabric errors):
#
#   Lakehouse READ  → spark.sql() or spark.read.format("delta")
#                     NOT synapsesql (hits SQL endpoint — has sync lag)
#
#   Lakehouse WRITE → df.write.format("delta").saveAsTable()
#                     NOT synapsesql (connector is write-to-warehouse only)
#
#   Warehouse WRITE → df.write.mode("overwrite").synapsesql("wh.dbo.table")
#                     synapsesql uses COPY INTO internally — scalable
#
#   Warehouse READ  → spark.read.synapsesql("wh.dbo.table")
#                     synapsesql reads through SQL engine — correct
#
# Usage:
#   # 1. Read from Lakehouse using spark.sql or Delta
#   lh_df = spark.sql("SELECT * FROM sales_data")
#
#   # 2. Write to Warehouse using synapsesql
#   lh_df.write.mode("overwrite").synapsesql("sales_warehouse.dbo.sales_data")
#
#   # 3. Read back from Warehouse using synapsesql
#   wh_df = spark.read.synapsesql("sales_warehouse.dbo.sales_data")
#
#   # 4. Validate
#   pv = PipelineValidator(
#           source_df    = lh_df,
#           target_df    = wh_df,
#           source_label = "Lakehouse",
#           target_label = "Warehouse",
#           key_cols     = ["order_id"],
#        )
#   pv.run_all_checks()
#
# Platform : Microsoft Fabric  (Runtime 1.3 — Spark 3.5, Delta 3.2)
# Author   : Myla Ram Reddy
# Version  : 3.0.0
# =============================================================================

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import NumericType
from datetime import datetime


# ── Print helpers ─────────────────────────────────────────────────────────────

def _banner(title: str):
    print("\n" + "=" * 62)
    print(f"  {title}")
    print("=" * 62)

def _pass(msg: str): print(f"  [PASS]  {msg}")
def _fail(msg: str): print(f"  [FAIL]  {msg}")
def _info(msg: str): print(f"  [INFO]  {msg}")
def _warn(msg: str): print(f"  [WARN]  {msg}")


# ── Standalone check functions (importable individually) ──────────────────────

def row_count_check(source_df: DataFrame, target_df: DataFrame) -> dict:
    """
    Compares row counts between source and target DataFrames.

    Args:
        source_df : PySpark DataFrame — from Lakehouse
        target_df : PySpark DataFrame — from Warehouse

    Returns:
        dict: source_count, target_count, difference, passed

    Example:
        r = row_count_check(lh_df, wh_df)
        # {'source_count': 10, 'target_count': 10, 'difference': 0, 'passed': True}
    """
    src  = source_df.count()
    tgt  = target_df.count()
    diff = src - tgt
    return {
        "source_count": src,
        "target_count": tgt,
        "difference"  : diff,
        "passed"      : diff == 0
    }


def column_count_check(source_df: DataFrame, target_df: DataFrame) -> dict:
    """
    Compares number of columns between source and target.

    Returns:
        dict: source_cols, target_cols, passed
    """
    src = len(source_df.columns)
    tgt = len(target_df.columns)
    return {
        "source_cols": src,
        "target_cols": tgt,
        "passed"     : src == tgt
    }


def schema_match_check(source_df: DataFrame, target_df: DataFrame) -> dict:
    """
    Checks column names and data types match between source and target.

    Returns:
        dict: missing_in_target, missing_in_source, type_mismatches, passed
    """
    src = {f.name: str(f.dataType) for f in source_df.schema.fields}
    tgt = {f.name: str(f.dataType) for f in target_df.schema.fields}

    missing_in_target = [c for c in src if c not in tgt]
    missing_in_source = [c for c in tgt if c not in src]
    type_mismatches   = [c for c in src if c in tgt and src[c] != tgt[c]]
    passed = (
        not missing_in_target and
        not missing_in_source and
        not type_mismatches
    )
    return {
        "missing_in_target": missing_in_target,
        "missing_in_source": missing_in_source,
        "type_mismatches"  : type_mismatches,
        "passed"           : passed
    }


def null_check(df: DataFrame, label: str = "DataFrame") -> dict:
    """
    Counts null values per column.

    Args:
        df    : PySpark DataFrame
        label : display label e.g. "Lakehouse" or "Warehouse"

    Returns:
        dict: label, nulls {col: count}, total_nulls, passed
    """
    nulls = {}
    for c in df.columns:
        n = df.select(
            F.sum(F.when(F.col(c).isNull(), 1).otherwise(0))
        ).collect()[0][0]
        nulls[c] = int(n) if n is not None else 0
    total = sum(nulls.values())
    return {
        "label"      : label,
        "nulls"      : nulls,
        "total_nulls": total,
        "passed"     : total == 0
    }


def duplicate_check(df: DataFrame,
                    key_cols: list = None,
                    label: str = "DataFrame") -> dict:
    """
    Counts duplicate rows.

    Args:
        df       : PySpark DataFrame
        key_cols : columns to check duplicates on (default: all columns)
        label    : display label

    Returns:
        dict: label, total_rows, distinct_rows, duplicates, passed
    """
    cols     = key_cols if key_cols else df.columns
    total    = df.count()
    distinct = df.select(cols).distinct().count()
    dupes    = total - distinct
    return {
        "label"        : label,
        "total_rows"   : total,
        "distinct_rows": distinct,
        "duplicates"   : dupes,
        "passed"       : dupes == 0
    }


def numeric_reconciliation(source_df: DataFrame,
                            target_df: DataFrame,
                            numeric_cols: list = None) -> dict:
    """
    Compares SUM, MIN, MAX, AVG on numeric columns between source and target.

    Args:
        source_df    : Lakehouse DataFrame
        target_df    : Warehouse DataFrame
        numeric_cols : list of column names (auto-detected if None)

    Returns:
        dict: results {col: {source, target, passed}}, passed
    """
    if numeric_cols is None:
        numeric_cols = [
            f.name for f in source_df.schema.fields
            if isinstance(f.dataType, NumericType)
        ]

    results, all_passed = {}, True

    for col in numeric_cols:
        if col not in source_df.columns or col not in target_df.columns:
            _warn(f"Column '{col}' not found in both DataFrames — skipping")
            continue

        def get_stats(df, c=col):
            return df.select(
                F.round(F.sum(F.col(c)), 2).alias("sum"),
                F.round(F.min(F.col(c)), 2).alias("min"),
                F.round(F.max(F.col(c)), 2).alias("max"),
                F.round(F.avg(F.col(c)), 2).alias("avg"),
            ).collect()[0]

        s = get_stats(source_df)
        t = get_stats(target_df)

        col_passed = (
            s["sum"] == t["sum"] and
            s["min"] == t["min"] and
            s["max"] == t["max"] and
            s["avg"] == t["avg"]
        )
        if not col_passed:
            all_passed = False

        results[col] = {
            "source": {"sum": s["sum"], "min": s["min"],
                       "max": s["max"], "avg": s["avg"]},
            "target": {"sum": t["sum"], "min": t["min"],
                       "max": t["max"], "avg": t["avg"]},
            "passed": col_passed
        }

    return {"results": results, "passed": all_passed}


def column_value_distribution(df: DataFrame,
                               col_name: str,
                               label: str = "DataFrame",
                               top_n: int = 5) -> dict:
    """
    Returns top N most frequent values for a column.

    Returns:
        dict: label, column, top_values [(value, count), ...]
    """
    top = (
        df.groupBy(col_name)
          .count()
          .orderBy(F.desc("count"))
          .limit(top_n)
          .collect()
    )
    return {
        "label"     : label,
        "column"    : col_name,
        "top_values": [(row[col_name], row["count"]) for row in top]
    }


# ── PipelineValidator class ───────────────────────────────────────────────────

class PipelineValidator:
    """
    Pipeline validator for Lakehouse → Warehouse reconciliation.

    Accepts two already-loaded PySpark DataFrames and runs 6 checks:
        1. Row count match
        2. Column count match
        3. Schema (column names + data types) match
        4. Null counts — source and target
        5. Duplicate rows — source and target
        6. Numeric SUM / MIN / MAX / AVG reconciliation

    Args:
        source_df    : DataFrame loaded from Lakehouse
                       (use spark.sql() or spark.read.format("delta"))
        target_df    : DataFrame loaded from Warehouse
                       (use spark.read.synapsesql())
        source_label : display name for source (default: "Lakehouse")
        target_label : display name for target (default: "Warehouse")
        key_cols     : columns for duplicate check (default: all columns)
        numeric_cols : columns for numeric reconciliation (default: auto-detect)

    Example:
        # Step 1 — load DataFrames correctly
        lh_df = spark.sql("SELECT * FROM sales_data")
        wh_df = spark.read.synapsesql("sales_warehouse.dbo.sales_data")

        # Step 2 — create validator and run
        pv = PipelineValidator(
            source_df    = lh_df,
            target_df    = wh_df,
            source_label = "Sales Lakehouse",
            target_label = "Sales Warehouse",
            key_cols     = ["order_id"],
            numeric_cols = ["amount", "quantity"],
        )
        pv.run_all_checks()
        summary = pv.get_summary()
    """

    def __init__(self,
                 source_df    : DataFrame,
                 target_df    : DataFrame,
                 source_label : str  = "Lakehouse",
                 target_label : str  = "Warehouse",
                 key_cols     : list = None,
                 numeric_cols : list = None):

        self.source_df    = source_df
        self.target_df    = target_df
        self.source_label = source_label
        self.target_label = target_label
        self.key_cols     = key_cols
        self.numeric_cols = numeric_cols
        self._results     = {}
        self._run_time    = None

    # ── Individual check methods ──────────────────────────────────────────────

    def check_row_count(self) -> dict:
        """Check 1 — Row counts must match."""
        _banner("CHECK 1 — Row Count Reconciliation")
        r = row_count_check(self.source_df, self.target_df)
        _info(f"{self.source_label} rows : {r['source_count']:,}")
        _info(f"{self.target_label} rows : {r['target_count']:,}")
        if r["passed"]:
            _pass("Row counts MATCH")
        else:
            direction = "source has more" if r["difference"] > 0 else "target has more"
            _fail(f"Row count MISMATCH — difference: {abs(r['difference']):,} rows ({direction})")
        self._results["row_count"] = r
        return r

    def check_column_count(self) -> dict:
        """Check 2 — Column counts must match."""
        _banner("CHECK 2 — Column Count Reconciliation")
        r = column_count_check(self.source_df, self.target_df)
        _info(f"{self.source_label} columns : {r['source_cols']}")
        _info(f"{self.target_label} columns : {r['target_cols']}")
        if r["passed"]:
            _pass("Column counts MATCH")
        else:
            _fail(f"Column count MISMATCH — "
                  f"source: {r['source_cols']}, target: {r['target_cols']}")
        self._results["column_count"] = r
        return r

    def check_schema(self) -> dict:
        """Check 3 — Column names and data types must match."""
        _banner("CHECK 3 — Schema Match (Column Names + Data Types)")
        r = schema_match_check(self.source_df, self.target_df)
        if r["missing_in_target"]:
            _fail(f"In {self.source_label} but NOT in {self.target_label} : "
                  f"{r['missing_in_target']}")
        if r["missing_in_source"]:
            _warn(f"Extra in {self.target_label} not in {self.source_label} : "
                  f"{r['missing_in_source']}")
        if r["type_mismatches"]:
            _fail(f"Data type mismatches on : {r['type_mismatches']}")
        if r["passed"]:
            _pass("Schema MATCHES — all column names and types align")
        self._results["schema"] = r
        return r

    def check_nulls(self) -> dict:
        """Check 4 — Null counts on source and target."""
        _banner("CHECK 4 — Null Count Check (Source and Target)")
        results = {}
        for df, label, key in [
            (self.source_df, self.source_label, "source"),
            (self.target_df, self.target_label, "target"),
        ]:
            r = null_check(df, label)
            _info(f"{label} — total nulls: {r['total_nulls']}")
            for col, cnt in r["nulls"].items():
                flag = "[OK]" if cnt == 0 else "[!!]"
                print(f"          {flag}  {col:<20} : {cnt} null(s)")
            if r["passed"]:
                _pass(f"No nulls in {label}")
            else:
                _fail(f"{label} has {r['total_nulls']} null(s) — see [!!] above")
            results[key] = r
        self._results["nulls"] = results
        return results

    def check_duplicates(self) -> dict:
        """Check 5 — Duplicate rows on source and target."""
        _banner("CHECK 5 — Duplicate Row Check (Source and Target)")
        key_info = str(self.key_cols) if self.key_cols else "all columns"
        _info(f"Checking duplicates on : {key_info}")
        results = {}
        for df, label, key in [
            (self.source_df, self.source_label, "source"),
            (self.target_df, self.target_label, "target"),
        ]:
            r = duplicate_check(df, self.key_cols, label)
            _info(f"{label} — "
                  f"total: {r['total_rows']:,}  "
                  f"distinct: {r['distinct_rows']:,}  "
                  f"duplicates: {r['duplicates']:,}")
            if r["passed"]:
                _pass(f"No duplicates in {label}")
            else:
                _fail(f"{label} has {r['duplicates']:,} duplicate row(s)")
            results[key] = r
        self._results["duplicates"] = results
        return results

    def check_numeric_reconciliation(self) -> dict:
        """Check 6 — SUM / MIN / MAX / AVG on numeric columns."""
        _banner("CHECK 6 — Numeric Reconciliation (SUM / MIN / MAX / AVG)")
        r = numeric_reconciliation(
            self.source_df, self.target_df, self.numeric_cols
        )
        if not r["results"]:
            _warn("No numeric columns found for reconciliation")
        else:
            src_lbl = self.source_label[:12]
            tgt_lbl = self.target_label[:12]
            print(f"  {'Column':<20} {'Metric':<8} "
                  f"{src_lbl:>14} {tgt_lbl:>14}  Match")
            print("  " + "-" * 68)
            for col, stats in r["results"].items():
                for metric in ["sum", "min", "max", "avg"]:
                    sv    = stats["source"][metric]
                    tv    = stats["target"][metric]
                    match = "OK" if sv == tv else "MISMATCH"
                    print(f"  {col:<20} {metric:<8} "
                          f"{str(sv):>14} {str(tv):>14}  {match}")
        if r["passed"]:
            _pass("All numeric columns reconcile between source and target")
        else:
            _fail("Numeric reconciliation FAILED — see MISMATCH rows above")
        self._results["numeric"] = r
        return r

    # ── Run all ───────────────────────────────────────────────────────────────

    def run_all_checks(self):
        """
        Runs all 6 validation checks sequentially and prints a final summary.
        """
        self._run_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print("\n" + "#" * 62)
        print("  PIPELINE VALIDATOR — Microsoft Fabric")
        print(f"  Source  : {self.source_label}")
        print(f"  Target  : {self.target_label}")
        print(f"  Run at  : {self._run_time}")
        print("#" * 62)

        self.check_row_count()
        self.check_column_count()
        self.check_schema()
        self.check_nulls()
        self.check_duplicates()
        self.check_numeric_reconciliation()
        self._print_summary()

    def _print_summary(self):
        """Prints final PASS / FAIL / SKIP summary table."""
        _banner("FINAL VALIDATION SUMMARY")

        check_map = {
            "Row count"              : self._results.get("row_count",   {}).get("passed"),
            "Column count"           : self._results.get("column_count",{}).get("passed"),
            "Schema match"           : self._results.get("schema",      {}).get("passed"),
            f"Nulls — {self.source_label}"     : self._results.get("nulls",{}).get("source",{}).get("passed"),
            f"Nulls — {self.target_label}"     : self._results.get("nulls",{}).get("target",{}).get("passed"),
            f"Duplicates — {self.source_label}": self._results.get("duplicates",{}).get("source",{}).get("passed"),
            f"Duplicates — {self.target_label}": self._results.get("duplicates",{}).get("target",{}).get("passed"),
            "Numeric reconciliation" : self._results.get("numeric",     {}).get("passed"),
        }

        passed = sum(1 for v in check_map.values() if v is True)
        failed = sum(1 for v in check_map.values() if v is False)

        print(f"  {'Check':<35} Result")
        print("  " + "-" * 46)
        for name, result in check_map.items():
            status = "PASS" if result is True else ("FAIL" if result is False else "SKIP")
            print(f"  {name:<35} {status}")
        print("  " + "-" * 46)
        print(f"  Total: {len(check_map)}  |  Passed: {passed}  |  Failed: {failed}")
        print("\n" + "=" * 62)
        if failed == 0:
            print("  PIPELINE VALIDATION PASSED")
        else:
            print(f"  PIPELINE VALIDATION FAILED — {failed} check(s) need attention")
        print("=" * 62 + "\n")

    def get_summary(self) -> dict:
        """
        Returns full results dict — use this to write audit logs to Lakehouse.

        Returns:
            dict: run_time, source_label, target_label, results
        """
        return {
            "run_time"    : self._run_time,
            "source_label": self.source_label,
            "target_label": self.target_label,
            "results"     : self._results
        }
