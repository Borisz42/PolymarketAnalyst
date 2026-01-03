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
            "id": "top-level-ignored-id",
            "events": [{"id": "test-event-id"}],
            "endDate": "2025-12-30T15:00:00Z",
        }
        self.mock_user_activity_response = [
            {
                "timestamp": 1767103200,
                "outcome": "Up",
                "size": "100.0",
                "price": "0.50",
            }
        ]
        self.source_target_time = '2025-12-30 15:00:00'

    @patch("pandas.read_csv")
    def test_get_slugs_for_date_success(self, mock_read_csv):
        mock_read_csv.return_value = self.mock_market_data_df
        slug_map = get_slugs_for_date("20251230")
        self.assertEqual(len(slug_map), 1)

    @patch("requests.get")
    def test_get_market_details_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = [self.mock_market_details_response]
        mock_get.return_value = mock_response
        details = get_market_details("test-slug")
        self.assertEqual(details["eventId"], "test-event-id")

    @patch("requests.get")
    def test_get_user_activity_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = self.mock_user_activity_response
        mock_get.return_value = mock_response
        activities = get_user_activity("test-event-id", TRACKED_USER_ADDRESS)
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities[0]["outcome"], "Up")

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
        self.assertEqual(trade["ExpirationTime"], "2025-12-30 15:00:00") # Verify reformatting

    @patch("src.data_collection.user_trade_collector.get_slugs_for_date")
    @patch("src.data_collection.user_trade_collector.get_market_details")
    @patch("src.data_collection.user_trade_collector.get_user_activity")
    @patch("pandas.DataFrame")
    def test_main_e2e(self, mock_dataframe_constructor, mock_get_activity, mock_get_details, mock_get_slugs):
        mock_get_slugs.return_value = {"test-slug": self.source_target_time}
        mock_get_details.return_value = {"eventId": "test-event-id", "expirationTime": "2025-12-30T15:00:00Z"}
        mock_get_activity.return_value = self.mock_user_activity_response

        with patch("sys.argv", ["script_name", "--date", "20251230"]):
            user_trade_collector_main()

        constructor_call_args = mock_dataframe_constructor.call_args_list[0].args[0]
        self.assertEqual(len(constructor_call_args), 1)
        self.assertEqual(constructor_call_args[0]["trade_side"], "Up")
        self.assertEqual(constructor_call_args[0]["quantity"], 100.0)

    @patch("requests.get")
    def test_get_user_activity_pagination(self, mock_get):
        """Test that get_user_activity handles pagination and sorting correctly."""
        # Create a mock response for a full page
        # Ensure timestamps are in a specific order to test sorting
        full_page_response = [{"timestamp": i, "outcome": "Up", "size": "1.0", "price": "0.5"} for i in range(1, 501)]
        # Create a mock response for the last page, with an unsorted timestamp to test sorting
        last_page_response = [{"timestamp": 502, "outcome": "Down", "size": "2.0", "price": "0.6"},
                              {"timestamp": 0, "outcome": "Down", "size": "2.0", "price": "0.6"}] # Timestamp 0 for testing sort

        # Set up the mock to return different values on subsequent calls
        mock_response1 = MagicMock()
        mock_response1.json.return_value = full_page_response
        mock_response1.raise_for_status.return_value = None

        mock_response2 = MagicMock()
        mock_response2.json.return_value = last_page_response
        mock_response2.raise_for_status.return_value = None

        mock_get.side_effect = [mock_response1, mock_response2]

        activities = get_user_activity("test-event-id", TRACKED_USER_ADDRESS)

        # Check that both requests were made
        self.assertEqual(mock_get.call_count, 2)
        
        # Check that the total number of activities is correct
        self.assertEqual(len(activities), 502)

        # Check that the activities are sorted by timestamp
        for i in range(len(activities) - 1):
            self.assertLessEqual(activities[i]["timestamp"], activities[i+1]["timestamp"],
                                 f"Activities not sorted at index {i}: {activities[i]['timestamp']} > {activities[i+1]['timestamp']}")

        # Verify specific items after sorting
        self.assertEqual(activities[0]["timestamp"], 0) # The one with timestamp 0 should be first
        self.assertEqual(activities[1]["timestamp"], 1)
        self.assertEqual(activities[501]["timestamp"], 502) # The one with timestamp 502 should be last

    @patch("requests.get")
    def test_get_user_activity_merging_duplicates(self, mock_get):
        """Test that get_user_activity correctly merges duplicates by summing their 'size'."""
        # Page 1 with a trade, 500 times
        page1_response = [{"timestamp": 100, "outcome": "Up", "size": "10.0", "price": "0.5"}] * 500
        # Page 2 with another trade that is a duplicate of the first one, and a new trade
        page2_response = [{"timestamp": 100, "outcome": "Up", "size": "15.0", "price": "0.5"},
                          {"timestamp": 200, "outcome": "Down", "size": "5.0", "price": "0.6"}]

        mock_response1 = MagicMock()
        mock_response1.json.return_value = page1_response
        mock_response1.raise_for_status.return_value = None
        
        mock_response2 = MagicMock()
        mock_response2.json.return_value = page2_response
        mock_response2.raise_for_status.return_value = None

        mock_get.side_effect = [mock_response1, mock_response2]

        activities = get_user_activity("test-event-id", TRACKED_USER_ADDRESS)

        # We expect 2 calls
        self.assertEqual(mock_get.call_count, 2)

        # We expect 2 activities after merging
        self.assertEqual(len(activities), 2)
        
        # The first activity should be the one with timestamp 100
        # and its size should be the sum of the duplicates (500 * 10.0 + 15.0 = 5015.0)
        activity1 = next(act for act in activities if act['timestamp'] == 100)
        self.assertEqual(float(activity1['size']), 5015.0)
        
        # The second activity should be the one with timestamp 200
        activity2 = next(act for act in activities if act['timestamp'] == 200)
        self.assertEqual(float(activity2['size']), 5.0)

        # Also check if the final list is sorted
        self.assertEqual(activities[0]['timestamp'], 100)
        self.assertEqual(activities[1]['timestamp'], 200)


if __name__ == "__main__":
    unittest.main()
