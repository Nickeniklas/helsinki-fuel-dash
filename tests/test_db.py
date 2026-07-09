"""Unit tests for db.py: upsert/dedupe/date-rollover. In-memory SQLite only,
no network -- fixture-driven tests exercise the real parser output."""

import unittest
from datetime import date
from pathlib import Path

import db
import parser as p

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
REFERENCE = date(2026, 7, 9)


def load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_bytes().decode("cp1252")


class ConnectTests(unittest.TestCase):
    def test_creates_schema(self):
        conn = db.connect(":memory:")
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        self.assertIn("stations", tables)
        self.assertIn("prices", tables)


class StationUpsertTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")

    def test_insert_new_station(self):
        db.upsert_station(self.conn, 1051, "St1, Lauttasaari", REFERENCE)
        row = self.conn.execute(
            "SELECT name, lat, lon, first_seen FROM stations WHERE station_id=1051"
        ).fetchone()
        self.assertEqual(row, ("St1, Lauttasaari", None, None, "2026-07-09"))

    def test_second_upsert_does_not_overwrite_first_seen_or_name(self):
        db.upsert_station(self.conn, 1051, "Original Name", REFERENCE)
        db.upsert_station(self.conn, 1051, "Different Name", date(2026, 7, 10))
        row = self.conn.execute(
            "SELECT name, first_seen FROM stations WHERE station_id=1051"
        ).fetchone()
        self.assertEqual(row, ("Original Name", "2026-07-09"))

    def test_missing_coords_lists_new_station(self):
        db.upsert_station(self.conn, 1051, "Station", REFERENCE)
        self.assertEqual(db.stations_missing_coords(self.conn), [1051])

    def test_missing_coords_excludes_stations_with_coords(self):
        db.upsert_station(self.conn, 1051, "Station", REFERENCE)
        db.set_station_coords(self.conn, 1051, 60.156120, 24.883408)
        self.assertEqual(db.stations_missing_coords(self.conn), [])


class CoordSanityTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")
        db.upsert_station(self.conn, 1051, "Station", REFERENCE)

    def test_valid_coords_stored(self):
        self.assertTrue(db.set_station_coords(self.conn, 1051, 60.156120, 24.883408))
        row = self.conn.execute(
            "SELECT lat, lon FROM stations WHERE station_id=1051"
        ).fetchone()
        self.assertEqual(row, (60.156120, 24.883408))

    def test_out_of_bbox_coords_rejected(self):
        with self.assertLogs("db", level="WARNING"):
            result = db.set_station_coords(self.conn, 1051, 40.0, 24.88)  # lat too low
        self.assertFalse(result)
        row = self.conn.execute(
            "SELECT lat, lon FROM stations WHERE station_id=1051"
        ).fetchone()
        self.assertEqual(row, (None, None))


class PriceUpsertTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.connect(":memory:")
        db.upsert_station(self.conn, 1051, "Station", REFERENCE)

    def test_insert_new_price(self):
        self.assertTrue(db.upsert_price(self.conn, 1051, "95", "2026-07-09", 2.099))
        row = self.conn.execute(
            "SELECT price FROM prices WHERE station_id=1051 AND fuel='95' AND date='2026-07-09'"
        ).fetchone()
        self.assertEqual(row, (2.099,))

    def test_same_day_reupsert_overwrites_latest_wins(self):
        db.upsert_price(self.conn, 1051, "95", "2026-07-09", 2.099)
        db.upsert_price(self.conn, 1051, "95", "2026-07-09", 2.059)
        rows = self.conn.execute(
            "SELECT price FROM prices WHERE station_id=1051 AND fuel='95' AND date='2026-07-09'"
        ).fetchall()
        self.assertEqual(rows, [(2.059,)])

    def test_out_of_bounds_price_rejected(self):
        with self.assertLogs("db", level="WARNING"):
            result = db.upsert_price(self.conn, 1051, "95", "2026-07-09", 5.00)
        self.assertFalse(result)
        count = self.conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
        self.assertEqual(count, 0)

    def test_different_fuel_and_date_do_not_collide(self):
        db.upsert_price(self.conn, 1051, "95", "2026-07-09", 2.099)
        db.upsert_price(self.conn, 1051, "98", "2026-07-09", 2.199)
        db.upsert_price(self.conn, 1051, "95", "2026-07-08", 2.089)
        count = self.conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
        self.assertEqual(count, 3)


class IngestRowsFixtureTests(unittest.TestCase):
    """Drives db.ingest_rows() with real parser output from a saved HTML
    fixture -- exercises upsert + dedupe + date resolution together."""

    def setUp(self):
        self.conn = db.connect(":memory:")
        self.rows = p.parse_page(load_fixture("helsinki.html"), reference=REFERENCE)

    def test_ingest_creates_one_station_row_per_station(self):
        db.ingest_rows(self.conn, self.rows, seen_on=REFERENCE)
        station_count = self.conn.execute("SELECT COUNT(*) FROM stations").fetchone()[0]
        self.assertEqual(station_count, len(self.rows))

    def test_ingest_is_idempotent(self):
        db.ingest_rows(self.conn, self.rows, seen_on=REFERENCE)
        db.ingest_rows(self.conn, self.rows, seen_on=REFERENCE)
        price_count = self.conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
        expected = sum(
            1 for row in self.rows for price in row["prices"].values() if price is not None
        )
        self.assertEqual(price_count, expected)

    def test_ingest_skips_null_prices(self):
        db.ingest_rows(self.conn, self.rows, seen_on=REFERENCE)
        # station 1983 has a None 98E price, per test_parser.py's fixture assertions
        count = self.conn.execute(
            "SELECT COUNT(*) FROM prices WHERE station_id=1983 AND fuel='98'"
        ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_resolved_dates_land_in_prices_table(self):
        db.ingest_rows(self.conn, self.rows, seen_on=REFERENCE)
        row = self.conn.execute(
            "SELECT date FROM prices WHERE station_id=1051 AND fuel='95'"
        ).fetchone()
        self.assertEqual(row[0], "2026-07-09")


class CrossPageDedupeTests(unittest.TestCase):
    """Same station re-ingested with a changed price, same day: overwrite, no dup row."""

    def test_reingesting_same_station_different_price_overwrites(self):
        conn = db.connect(":memory:")
        row = {
            "station_id": 1051,
            "station_name": "St1, Lauttasaari Heikkiläntie 12",
            "date": "2026-07-09",
            "prices": {"95": 2.099, "98": 2.199, "dsl": 2.129},
        }
        db.ingest_rows(conn, [row], seen_on=REFERENCE)
        updated_row = dict(row, prices={"95": 2.059, "98": 2.199, "dsl": 2.129})
        db.ingest_rows(conn, [updated_row], seen_on=REFERENCE)

        price = conn.execute(
            "SELECT price FROM prices WHERE station_id=1051 AND fuel='95' AND date='2026-07-09'"
        ).fetchone()[0]
        self.assertEqual(price, 2.059)
        count = conn.execute(
            "SELECT COUNT(*) FROM prices WHERE station_id=1051"
        ).fetchone()[0]
        self.assertEqual(count, 3)


class DateRolloverIngestTests(unittest.TestCase):
    """resolve_date()'s year-rollover output must dedupe/store correctly once ingested."""

    def test_rollover_resolved_date_stored_correctly(self):
        reference = date(2026, 1, 2)
        resolved = p.resolve_date("31.12.", reference)
        self.assertEqual(resolved, date(2025, 12, 31))

        conn = db.connect(":memory:")
        row = {
            "station_id": 9001,
            "station_name": "Rollover Test Station",
            "date": resolved.isoformat(),
            "prices": {"95": 2.10, "98": None, "dsl": None},
        }
        db.ingest_rows(conn, [row], seen_on=reference)
        stored_date = conn.execute(
            "SELECT date FROM prices WHERE station_id=9001"
        ).fetchone()[0]
        self.assertEqual(stored_date, "2025-12-31")


if __name__ == "__main__":
    unittest.main()
