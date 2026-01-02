import unittest
from unittest.mock import patch, Mock
import json
import datetime
import pytz

from src.data_collection.websocket_logger import get_market_info

class TestWebsocketLogger(unittest.TestCase):

    @patch('requests.get')
    def test_get_market_info_success(self, mock_get):
        # Create a mock response object
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None

        # Sample API response data with endDate
        api_data = [{
            "markets": [{
                "conditionId": "0x123456789",
                "clobTokenIds": "[\"token_up\", \"token_down\"]",
                "endDate": "2026-01-02T18:30:00Z"
            }]
        }]
        mock_response.json.return_value = api_data
        mock_get.return_value = mock_response

        # Call the function with a dummy slug
        condition_id, clob_token_ids, expiration_time = get_market_info("dummy-slug")

        # Assert that the function returns the correct values
        self.assertEqual(condition_id, "0x123456789")
        self.assertEqual(clob_token_ids, ["token_up", "token_down"])

        # Check the expiration time
        expected_time = datetime.datetime(2026, 1, 2, 18, 30, 0, tzinfo=pytz.utc)
        self.assertEqual(expiration_time, expected_time)

        mock_get.assert_called_once_with(
            "https://gamma-api.polymarket.com/events",
            params={"slug": "dummy-slug"},
            timeout=10
        )

    @patch('requests.get')
    def test_get_market_info_no_data(self, mock_get):
        # Mock an empty response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        condition_id, clob_token_ids, expiration_time = get_market_info("dummy-slug")

        self.assertIsNone(condition_id)
        self.assertIsNone(clob_token_ids)
        self.assertIsNone(expiration_time)

    @patch('requests.get')
    def test_get_market_info_missing_keys(self, mock_get):
        # Mock a response with missing keys
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        api_data = [{"markets": [{}]}] # Missing all keys
        mock_response.json.return_value = api_data
        mock_get.return_value = mock_response

        condition_id, clob_token_ids, expiration_time = get_market_info("dummy-slug")

        self.assertIsNone(condition_id)
        self.assertIsNone(clob_token_ids)
        self.assertIsNone(expiration_time)

if __name__ == '__main__':
    unittest.main()
