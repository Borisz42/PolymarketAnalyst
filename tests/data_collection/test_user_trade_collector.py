import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import requests

# Add project root to path for absolute imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.data_collection.user_trade_collector import (
    get_slugs_for_date,
    get_market_details,
    get_user_activity,
    process_trades,
    main as user_trade_collector_main,
)
from src.config import TRACKED_USER_ADDRESS

class TestUserTradeCollector(unittest.TestCase):

    def setUp(self):
        """Set up common test data."""
        self.mock_market_data_df = pd.DataFrame({
            'Timestamp': ['2025-12-30 14:00:00', '2025-12-30 14:00:01'],
            'TargetTime': ['2025-12-30 15:00:00', '2025-12-30 15:00:00'],
        })
        self.mock_market_details_response = {
            "event": {"id": "test-event-id"},
            "endDate": "2025-12-30T15:00:00Z",
        }
        self.mock_user_activity_response = [
            {
                "timestamp": "2025-12-30T14:00:00Z",
                "outcome_name": "Up",
                "size_in_usd": "100.0",
                "price": "0.50",
            }
        ]
        self.source_target_time = '2025-12-30 15:00:00'

    @patch("pandas.read_csv")
    def test_get_slugs_for_date_success(self, mock_read_csv):
        mock_read_csv.return_value = self.mock_market_data_df
        slug_map = get_slugs_for_date("20251230")
        self.assertEqual(len(slug_map), 1)
        slug = list(slug_map.keys())[0]
        self.assertIn("btc-updown-15m-", slug)
        self.assertEqual(slug_map[slug], self.source_target_time)

    @patch("requests.get")
    def test_get_market_details_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = [self.mock_market_details_response]
        mock_get.return_value = mock_response
        details = get_market_details("test-slug")
        self.assertIsNotNone(details)
        self.assertEqual(details["eventId"], "test-event-id")
        mock_get.assert_called_with(
            "https://gamma-api.polymarket.com/markets",
            params={"slug": "test-slug"},
            timeout=10
        )

    @patch("requests.get")
    def test_get_user_activity_success(self, mock_get):
        """Test successful fetching of user activity from the Data API."""
        mock_response = MagicMock()
        mock_response.json.return_value = self.mock_user_activity_response
        mock_get.return_value = mock_response

        activities = get_user_activity("test-event-id", TRACKED_USER_ADDRESS)
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities[0]["outcome_name"], "Up")

        expected_params = {
            "eventId": "test-event-id",
            "user": TRACKED_USER_ADDRESS,
            "limit": 1000,
            "type": "TRADE",
        }
        mock_get.assert_called_with(
            "https://data-api.polymarket.com/activity",
            params=expected_params,
            timeout=10
        )

    def test_process_trades(self):
        """Test correct processing of raw trade data from the Data API."""
        market_details = {"expirationTime": "2025-12-30T15:00:00Z"}
        processed = process_trades(
            self.mock_user_activity_response,
            market_details,
            self.source_target_time
        )
        self.assertEqual(len(processed), 1)
        trade = processed[0]
        self.assertEqual(trade["timestamp"], "2025-12-30 14:00:00")
        self.assertEqual(trade["trade_side"], "Up")
        self.assertEqual(trade["quantity"], 100.0)
        self.assertEqual(trade["price"], 0.50)
        self.assertEqual(trade["TargetTime"], self.source_target_time)

    @patch("src.data_collection.user_trade_collector.get_slugs_for_date")
    @patch("src.data_collection.user_trade_collector.get_market_details")
    @patch("src.data_collection.user_trade_collector.get_user_activity")
    @patch("pandas.DataFrame")
    def test_main_e2e(self, mock_dataframe_constructor, mock_get_activity, mock_get_details, mock_get_slugs):
        mock_get_slugs.return_value = {"test-slug": self.source_target_time}
        mock_get_details.return_value = {"eventId": "test-event-id"}
        mock_get_activity.return_value = self.mock_user_activity_response

        with patch("sys.argv", ["script_name", "--date", "20251230"]):
            user_trade_collector_main()

        constructor_call_args = mock_dataframe_constructor.call_args_list[0].args[0]
        self.assertEqual(len(constructor_call_args), 1)
        self.assertEqual(constructor_call_args[0]["TargetTime"], self.source_target_time)

if __name__ == "__main__":
    unittest.main()
