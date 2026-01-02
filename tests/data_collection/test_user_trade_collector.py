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

class TestUserTradeCollector(unittest.TestCase):

    def setUp(self):
        """Set up common test data."""
        self.mock_market_data_df = pd.DataFrame({
            'Timestamp': ['2025-12-30 14:00:00', '2025-12-30 14:00:01'],
            'TargetTime': ['2025-12-30 15:00:00', '2025-12-30 15:00:00'],
            'UpAsk': [0.5, 0.51],
            'UpBid': [0.49, 0.50]
        })
        self.mock_market_details_response = {
            "event": {"id": "test-event-id"},
            "endDate": "2025-12-30T15:00:00Z",
            "startDate": "2025-12-30T14:45:00Z", # This is ignored, but kept for realism
        }
        self.mock_user_activity_response = {
            "activities": [
                {
                    "timestamp": "1767103200000000",
                    "side": "buy",
                    "quantity": "100",
                    "price": "0.50",
                }
            ]
        }
        self.source_target_time = '2025-12-30 15:00:00'

    @patch("pandas.read_csv")
    def test_get_slugs_for_date_success(self, mock_read_csv):
        """Test successful slug and TargetTime mapping from a CSV file."""
        mock_read_csv.return_value = self.mock_market_data_df

        slug_map = get_slugs_for_date("20251230")
        self.assertEqual(len(slug_map), 1)
        slug = list(slug_map.keys())[0]
        self.assertIn("btc-updown-15m-", slug)
        self.assertEqual(slug_map[slug], self.source_target_time)

    @patch("pandas.read_csv", side_effect=FileNotFoundError)
    def test_get_slugs_for_date_file_not_found(self, mock_read_csv):
        """Test graceful failure when the market data file is not found."""
        slug_map = get_slugs_for_date("20251230")
        self.assertEqual(slug_map, {})

    @patch("requests.get")
    def test_get_market_details_success(self, mock_get):
        """Test successful fetching of market details."""
        mock_response = MagicMock()
        mock_response.json.return_value = self.mock_market_details_response
        mock_get.return_value = mock_response

        details = get_market_details("test-slug")
        self.assertIsNotNone(details)
        self.assertEqual(details["eventId"], "test-event-id")

    @patch("requests.get", side_effect=requests.RequestException("API Error"))
    def test_get_market_details_api_error(self, mock_get):
        """Test graceful failure on market details API error."""
        details = get_market_details("test-slug")
        self.assertIsNone(details)

    @patch("requests.get")
    def test_get_user_activity_success(self, mock_get):
        """Test successful fetching of user activity."""
        mock_response = MagicMock()
        mock_response.json.return_value = self.mock_user_activity_response
        mock_get.return_value = mock_response

        activities = get_user_activity("test-event-id", "test-user")
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities[0]["side"], "buy")

    def test_process_trades(self):
        """Test correct processing of raw trade data with the source TargetTime."""
        market_details = {
            "expirationTime": "2025-12-30T15:00:00Z",
        }
        processed = process_trades(
            self.mock_user_activity_response["activities"],
            market_details,
            self.source_target_time
        )
        self.assertEqual(len(processed), 1)
        trade = processed[0]
        self.assertEqual(trade["timestamp"], "2025-12-30 14:00:00")
        self.assertEqual(trade["trade_side"], "buy")
        self.assertEqual(trade["TargetTime"], self.source_target_time) # Key assertion

    @patch("src.data_collection.user_trade_collector.get_slugs_for_date")
    @patch("src.data_collection.user_trade_collector.get_market_details")
    @patch("src.data_collection.user_trade_collector.get_user_activity")
    @patch("pandas.DataFrame")
    def test_main_e2e(self, mock_dataframe_constructor, mock_get_activity, mock_get_details, mock_get_slugs):
        """Test the main function end-to-end with the new data structure."""
        # Setup mocks
        mock_get_slugs.return_value = {"test-slug": self.source_target_time}
        mock_get_details.return_value = {
            "eventId": "test-event-id",
            "expirationTime": "2025-12-30T15:00:00Z",
        }
        mock_get_activity.return_value = self.mock_user_activity_response["activities"]

        # Run main function with mocked args
        with patch("sys.argv", ["script_name", "--date", "20251230"]):
            user_trade_collector_main()

        # Assertions
        mock_get_slugs.assert_called_with("20251230")
        mock_get_details.assert_called_with("test-slug")
        mock_get_activity.assert_called_with("test-event-id", unittest.mock.ANY)

        # Check the data passed to the DataFrame constructor
        constructor_call_args = mock_dataframe_constructor.call_args_list[0].args[0]
        self.assertEqual(len(constructor_call_args), 1)
        self.assertEqual(constructor_call_args[0]["TargetTime"], self.source_target_time)


if __name__ == "__main__":
    unittest.main()
