# Test methods with long descriptive names can omit docstrings
# pylint: disable=missing-docstring

import unittest
import inspect
import pkgutil
import traceback

import Orange
from Orange.data import Table, Variable
from Orange.regression import Learner
from Orange.data.table import dataset_dirs


class RegressionLearnersTest(unittest.TestCase):
    def setUp(self):
        Variable._clear_all_caches()
        dataset_dirs.append("Orange/tests")

    def tearDown(self):
        dataset_dirs.pop()

    def all_learners(self):
        regression_modules = pkgutil.walk_packages(
            path=Orange.regression.__path__,
            prefix="Orange.regression.",
            onerror=lambda x: None)
        for importer, modname, ispkg in regression_modules:
            try:
                module = pkgutil.importlib.import_module(modname)
            except ImportError:
                continue

            for name, class_ in inspect.getmembers(module, inspect.isclass):
                if issubclass(class_, Learner) and 'base' not in class_.__module__:
                    yield class_

    def test_adequacy_all_learners(self):
        for learner in self.all_learners():
            try:
                learner = learner()
                table = Table("iris")
                self.assertRaises(ValueError, learner, table)
            except TypeError as err:
                traceback.print_exc()
                continue

    def test_adequacy_all_learners_multiclass(self):
        for learner in self.all_learners():
            try:
                learner = learner()
                table = Table("test8.tab")
                self.assertRaises(ValueError, learner, table)
            except TypeError as err:
                traceback.print_exc()
                continue


class MissingValuesTest(unittest.TestCase):
    def test_missing_class(self):
        table = Table("imports-85")
        for learner in RegressionLearnersTest().all_learners():
            try:
                learner = learner()
                model = learner(table)
                model(table)
            except TypeError:
                traceback.print_exc()
                continue
