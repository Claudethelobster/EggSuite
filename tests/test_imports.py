import unittest
import importlib

class TestEggSuiteImports(unittest.TestCase):
    def test_top_level_package(self):
        import egg_suite
        self.assertTrue(hasattr(egg_suite, '__version__'))
        self.assertTrue(hasattr(egg_suite, 'main'))
        self.assertTrue(hasattr(egg_suite, 'run'))

    def test_core_modules(self):
        modules = [
            'egg_suite.core.constants',
            'egg_suite.core.data_loader',
            'egg_suite.core.file_editor',
            'egg_suite.core.history_engine',
            'egg_suite.core.plugin_manager',
            'egg_suite.core.workspace',
        ]
        for mod in modules:
            with self.subTest(module=mod):
                m = importlib.import_module(mod)
                self.assertIsNotNone(m)

    def test_utils_modules(self):
        modules = [
            'egg_suite.utils.function_io',
            'egg_suite.utils.matplot_translator',
        ]
        for mod in modules:
            with self.subTest(module=mod):
                m = importlib.import_module(mod)
                self.assertIsNotNone(m)

    def test_ui_and_apps_modules(self):
        import os
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        modules = [
            'egg_suite.ui.theme',
            'egg_suite.ui.custom_widgets',
            'egg_suite.ui.splash_screen',
            'egg_suite.apps.hub.main_menu',
            'egg_suite.apps.plot_and_stats.main_window',
            'egg_suite.apps.data_inspector.inspector_window',
            'egg_suite.apps.settings.settings',
        ]
        for mod in modules:
            with self.subTest(module=mod):
                m = importlib.import_module(mod)
                self.assertIsNotNone(m)

if __name__ == '__main__':
    unittest.main()
