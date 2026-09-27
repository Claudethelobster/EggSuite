import unittest
from PyQt6.QtCore import QCoreApplication

# Ensure QCoreApplication instance for QObject signals
app = QCoreApplication.instance() or QCoreApplication(["test"])

from egg_suite.core.workspace import GlobalWorkspace

class TestWorkspace(unittest.TestCase):
    def setUp(self):
        self.ws = GlobalWorkspace()

    def test_add_and_remove_single_file(self):
        fake_data = {'col1': [1, 2, 3]}
        self.ws.add_single_file('/path/to/test.csv', fake_data)
        
        self.assertIn('/path/to/test.csv', self.ws.datasets)
        info = self.ws.get_item_info('/path/to/test.csv')
        self.assertIsNotNone(info)
        self.assertEqual(info['name'], 'test.csv')
        self.assertEqual(info['dataset'], fake_data)

        self.ws.remove_dataset('/path/to/test.csv')
        self.assertNotIn('/path/to/test.csv', self.ws.datasets)

if __name__ == '__main__':
    unittest.main()
