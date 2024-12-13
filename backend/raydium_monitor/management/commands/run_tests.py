from django.core.management.base import BaseCommand
import unittest
import sys
from raydium_monitor.tests import TestRaydiumPairTracker

class Command(BaseCommand):
    help = 'Run Raydium Monitor tests'

    def handle(self, *args, **options):
        # Create a test suite
        suite = unittest.TestLoader().loadTestsFromTestCase(TestRaydiumPairTracker)
        
        # Run the tests
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        # Set exit code based on test result
        sys.exit(not result.wasSuccessful())
