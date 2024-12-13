import unittest
import json
from datetime import datetime
from websocket_monitor import RaydiumPairTracker

class TestRaydiumPairTracker(unittest.TestCase):
    def setUp(self):
        self.tracker = RaydiumPairTracker()

    def test_extract_transaction_details(self):
        # Sample log details for testing
        sample_log_details = {
            'signature': 'test_signature',
            'err': None,
            'context': {'slot': 12345},
            'logs': [
                'Program log: RaydiumSwap amount_in: 1000, amount_out: 2000',
                'Program log: Swap successful'
            ]
        }

        transaction_info = self.tracker.extract_transaction_details(sample_log_details)
        
        # Validate transaction details
        self.assertIsNotNone(transaction_info)
        self.assertEqual(transaction_info['signature'], 'test_signature')
        self.assertEqual(transaction_info['status'], 'success')
        self.assertEqual(transaction_info['slot'], 12345)
        
        # Check swap details
        swap_details = transaction_info['swap_details']
        self.assertEqual(swap_details['dex'], 'Raydium')
        self.assertEqual(swap_details['amount_in'], 1000)
        self.assertEqual(swap_details['amount_out'], 2000)

    def test_parse_swap_details(self):
        # Sample log details with swap information
        sample_log_details = {
            'logs': [
                'Program log: RaydiumSwap amount_in: 500, amount_out: 1000',
                'Program log: Tokens: SOL, USDC'
            ]
        }

        swap_details = self.tracker.parse_swap_details(sample_log_details)
        
        self.assertEqual(swap_details['dex'], 'Raydium')
        self.assertEqual(swap_details['amount_in'], 500)
        self.assertEqual(swap_details['amount_out'], 1000)

    def test_failed_transaction(self):
        # Sample failed transaction log
        failed_log_details = {
            'signature': 'failed_signature',
            'err': {'InstructionError': [2, {'Custom': 6001}]},
            'context': {'slot': 67890},
            'logs': [
                'Program log: Transaction failed',
                'Program log: Slippage tolerance exceeded'
            ]
        }

        transaction_info = self.tracker.extract_transaction_details(failed_log_details)
        
        self.assertIsNotNone(transaction_info)
        self.assertEqual(transaction_info['signature'], 'failed_signature')
        self.assertEqual(transaction_info['status'], 'failed')
        self.assertEqual(transaction_info['slot'], 67890)
        self.assertIn('Slippage tolerance exceeded', str(transaction_info['logs']))

                }
            },
            "timestamp": "2023-06-15T12:00:00Z"
        }
        
        pool_info = self.monitor.extract_pool_info(mock_transaction)
        
        self.assertIsNotNone(pool_info, "Pool info extraction failed")
        self.assertEqual(pool_info['pool_address'], "test_pool_address", "Incorrect pool address extraction")

def run_tests():
    """Run all tests"""
    test_suite = unittest.TestLoader().loadTestsFromTestCase(TestRaydiumPoolMonitor)
    test_runner = unittest.TextTestRunner(verbosity=2)
    result = test_runner.run(test_suite)
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)
