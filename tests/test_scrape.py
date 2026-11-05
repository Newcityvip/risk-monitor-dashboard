import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"

if importlib.util.find_spec("requests") is None:
    sys.modules["requests"] = types.SimpleNamespace(Session=mock.Mock)

SPEC = importlib.util.spec_from_file_location("scrape", ROOT / "scripts" / "scrape.py")
scrape = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scrape)


def load_fixture(name):
    with (FIXTURES / name).open(encoding="utf-8") as fixture:
        return json.load(fixture)


class ScrapeRegressionTests(unittest.TestCase):
    def setUp(self):
        self.deposit = load_fixture("deposit_fw.json")
        self.withdrawal = load_fixture("withdrawal_fw.json")

    def build_latest(self, deposit=None, withdrawal=None):
        responses = [
            self.deposit if deposit is None else deposit,
            self.withdrawal if withdrawal is None else withdrawal,
        ]
        with mock.patch.object(scrape, "fetch_api", side_effect=responses):
            return scrape.build_latest()

    def test_fw_is_an_mcw_brand_with_comma_counts_and_decimal_amounts(self):
        latest = self.build_latest()
        fw = latest["brands"]["FW"]

        self.assertEqual("MCW", fw["group"])
        self.assertEqual(1250.0, fw["deposit_count"])
        self.assertEqual(125678.91, fw["deposit_amount"])
        self.assertEqual(350.0, fw["withdrawal_count"])
        self.assertEqual(65432.19, fw["withdrawal_amount"])
        self.assertAlmostEqual(60246.72, fw["net_flow"])

    def test_fw_parser_considers_every_time_slot_regardless_of_table_order(self):
        deposit_point = scrape.latest_non_zero_point(self.deposit["FW"], "deposit")
        withdrawal_point = scrape.latest_non_zero_point(self.withdrawal["FW"], "withdrawal")

        self.assertEqual(["17:00", "01:00", "23:59", "16:00"], list(self.deposit["FW"]["2026-11-05"]))
        self.assertEqual("23:59", deposit_point["hour"])
        self.assertEqual("23:59", withdrawal_point["hour"])
        self.assertEqual(125678.91, deposit_point["amount"])
        self.assertEqual(65432.19, withdrawal_point["amount"])

    def test_temporarily_missing_fw_is_zero_filled_without_breaking_scrape(self):
        deposit = dict(self.deposit)
        withdrawal = dict(self.withdrawal)
        deposit.pop("FW")
        withdrawal.pop("FW")

        latest = self.build_latest(deposit, withdrawal)
        fw = latest["brands"]["FW"]

        self.assertEqual(0, fw["deposit_count"])
        self.assertEqual(0, fw["deposit_amount"])
        self.assertEqual(0, fw["withdrawal_count"])
        self.assertEqual(0, fw["withdrawal_amount"])
        self.assertIsNone(fw["deposit_time"])
        self.assertIsNone(fw["withdrawal_time"])

    def test_unexpected_brand_is_ignored_and_existing_brands_are_unchanged(self):
        latest = self.build_latest()

        self.assertNotIn("EXTRA", latest["brands"])
        self.assertEqual(300000.75, latest["brands"]["M1"]["deposit_amount"])
        self.assertEqual(100000.50, latest["brands"]["M1"]["withdrawal_amount"])
        self.assertEqual(200000.25, latest["brands"]["CX"]["deposit_amount"])
        self.assertEqual(90000.10, latest["brands"]["CX"]["withdrawal_amount"])


if __name__ == "__main__":
    unittest.main()
