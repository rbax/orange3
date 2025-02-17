# Test methods with long descriptive names can omit docstrings
# pylint: disable=missing-docstring

import unittest
import numpy as np
import Orange

from Orange.classification import NaiveBayesLearner, MajorityLearner
from Orange.classification.majority import ConstantModel
from Orange.classification.naive_bayes import NaiveBayesModel
from Orange.regression import LinearRegressionLearner, MeanLearner
from Orange.data import Table
from Orange.evaluation import CrossValidation, LeaveOneOut, TestOnTrainingData, TestOnTestData, ShuffleSplit
from Orange.preprocess import discretize, preprocess


def random_data(nrows, ncols):
    np.random.seed(42)
    x = np.random.random_integers(0, 1, (nrows, ncols))
    col = np.random.randint(ncols)
    y = x[:nrows, col].reshape(nrows, 1)
    table = Table(x, y)
    table = preprocess.Discretize(discretize.EqualWidth(n=3))(table)
    return table


class TestingTestCase(unittest.TestCase):
    def test_no_data(self):
        self.assertRaises(TypeError, CrossValidation,
                          learners=[NaiveBayesLearner()])


# noinspection PyUnresolvedReferences
class CommonSamplingTests:
    def run_test_failed(self, method, succ_calls):
        # Can't use mocking helpers here (wrong result type for Majority,
        # exception caught for fails)
        def major(*args):
            nonlocal major_call
            major_call += 1
            return MajorityLearner()(*args)

        def fails(_):
            nonlocal fail_calls
            fail_calls += 1
            raise SystemError("failing learner")

        major_call = 0
        fail_calls = 0
        res = method(random_data(50, 4), [major, fails, major])
        self.assertFalse(res.failed[0])
        self.assertIsInstance(res.failed[1], Exception)
        self.assertFalse(res.failed[2])
        self.assertEqual(major_call, succ_calls)
        self.assertEqual(fail_calls, 1)

    def run_test_callback(self, method, expected_progresses):
        def record_progress(p):
            progress.append(p)
        progress = []
        method(random_data(50, 4), [MajorityLearner(), MajorityLearner()],
               callback=record_progress)
        np.testing.assert_almost_equal(np.array(progress), expected_progresses)

    def run_test_preprocessor(self, method, expected_sizes):
        def preprocessor(data):
            data_sizes.append(len(data))
            return data
        data_sizes = []
        method(Table('iris'), [MajorityLearner(), MajorityLearner()],
               preprocessor=preprocessor)
        self.assertEqual(data_sizes, expected_sizes)


class CrossValidationTestCase(unittest.TestCase, CommonSamplingTests):
    @classmethod
    def setUpClass(cls):
        cls.iris = Table('iris')

    def test_results(self):
        nrows, ncols = 1000, 10
        t = random_data(nrows, ncols)
        res = CrossValidation(t, [NaiveBayesLearner()])
        y = t.Y
        np.testing.assert_equal(res.actual, y[res.row_indices].reshape(nrows))
        np.testing.assert_equal(res.predicted[0],
                                y[res.row_indices].reshape(nrows))
        np.testing.assert_equal(np.argmax(res.probabilities[0], axis=1),
                                y[res.row_indices].reshape(nrows))
        self.assertEqual(len(res.folds), 10)
        for i, fold in enumerate(res.folds):
            self.assertAlmostEqual(fold.start, i * 100, delta=3)
            self.assertAlmostEqual(fold.stop, (i + 1) * 100, delta=3)

    def test_folds(self):
        nrows, ncols = 1000, 10
        t = random_data(nrows, ncols)
        res = CrossValidation(t, [NaiveBayesLearner()], k=5)
        self.assertEqual(len(res.folds), 5)
        for i, fold in enumerate(res.folds):
            self.assertAlmostEqual(fold.start, i * 200, delta=3)
            self.assertAlmostEqual(fold.stop, (i + 1) * 200, delta=3)

    def test_call_5(self):
        nrows, ncols = 1000, 10
        t = random_data(nrows, ncols)
        res = CrossValidation(t, [NaiveBayesLearner()], k=5)
        y = t.Y
        np.testing.assert_equal(res.actual, y[res.row_indices].reshape(nrows))
        np.testing.assert_equal(res.predicted[0],
                                y[res.row_indices].reshape(nrows))
        np.testing.assert_equal(np.argmax(res.probabilities[0], axis=1),
                                y[res.row_indices].reshape(nrows))
        self.assertEqual(len(res.folds), 5)
        for i, fold in enumerate(res.folds):
            self.assertAlmostEqual(fold.start, i * 200, delta=3)
            self.assertAlmostEqual(fold.stop, (i + 1) * 200, delta=3)

    def test_store_data(self):
        nrows, ncols = 100, 10
        t = random_data(nrows, ncols)
        learners = [NaiveBayesLearner()]

        res = CrossValidation(t, learners)
        self.assertIsNone(res.data)

        res = CrossValidation(t, learners, store_data=True)
        self.assertIs(res.data, t)

    def test_store_models(self):
        nrows, ncols = 100, 10
        t = random_data(nrows, ncols)
        learners = [NaiveBayesLearner(), MajorityLearner()]

        res = CrossValidation(t, learners, k=5)
        self.assertIsNone(res.models)

        res = CrossValidation(t, learners, k=5, store_models=True)
        self.assertEqual(len(res.models), 5)
        for models in res.models:
            self.assertEqual(len(models), 2)
            self.assertIsInstance(models[0], NaiveBayesModel)
            self.assertIsInstance(models[1], ConstantModel)

    def test_10_fold_probs(self):
        learners = [MajorityLearner(), MajorityLearner()]

        results = CrossValidation(self.iris[30:130], learners, k=10)

        self.assertEqual(results.predicted.shape, (2, len(self.iris[30:130])))
        np.testing.assert_equal(results.predicted, np.ones((2, 100)))
        probs = results.probabilities
        self.assertTrue((probs[:, :, 0] < probs[:, :, 2]).all())
        self.assertTrue((probs[:, :, 2] < probs[:, :, 1]).all())

    def test_miss_majority(self):
        x = np.zeros((50, 3))
        y = x[:, -1]
        x[-4:] = np.ones((4, 3))
        data = Table(x, y)
        res = CrossValidation(data, [MajorityLearner()], k=3)
        np.testing.assert_equal(res.predicted[0][:49], 0)

        x[-4:] = np.zeros((4, 3))
        res = CrossValidation(data, [MajorityLearner()], k=3)
        np.testing.assert_equal(res.predicted[0][:49], 0)

    def test_too_many_folds(self):
        w = []
        res = CrossValidation(self.iris, [MajorityLearner()], k=len(self.iris)/2, warnings=w)
        self.assertGreater(len(w), 0)

    def test_failed(self):
        self.run_test_failed(CrossValidation, 20)

    def test_callback(self):
        self.run_test_callback(CrossValidation, np.arange(0, 1.05, 0.05))

    def test_preprocessor(self):
        self.run_test_preprocessor(CrossValidation, [135] * 10)


class LeaveOneOutTestCase(unittest.TestCase, CommonSamplingTests):
    def test_results(self):
        nrows, ncols = 100, 10
        t = random_data(nrows, ncols)
        res = LeaveOneOut(t, [NaiveBayesLearner()])
        y = t.Y
        np.testing.assert_equal(res.actual, y[res.row_indices].reshape(nrows))
        np.testing.assert_equal(res.predicted[0],
                                y[res.row_indices].reshape(nrows))
        np.testing.assert_equal(np.argmax(res.probabilities[0], axis=1),
                                y[res.row_indices].reshape(nrows))
        np.testing.assert_equal(res.row_indices, np.arange(nrows))

    def test_call(self):
        nrows, ncols = 100, 10
        t = random_data(nrows, ncols)
        res = LeaveOneOut(t, [NaiveBayesLearner()])
        y = t.Y
        np.testing.assert_equal(res.actual, y[res.row_indices].reshape(nrows))
        np.testing.assert_equal(res.predicted[0],
                                y[res.row_indices].reshape(nrows))
        np.testing.assert_equal(np.argmax(res.probabilities[0], axis=1),
                                y[res.row_indices].reshape(nrows))

    def test_store_data(self):
        nrows, ncols = 50, 10
        t = random_data(nrows, ncols)
        learners = [NaiveBayesLearner()]

        res = LeaveOneOut(t, learners)
        self.assertIsNone(res.data)

        res = LeaveOneOut(t, learners, store_data=True)
        self.assertIs(res.data, t)

    def test_store_models(self):
        nrows, ncols = 50, 10
        t = random_data(nrows, ncols)
        learners = [NaiveBayesLearner(), MajorityLearner()]

        res = LeaveOneOut(t, learners)
        self.assertIsNone(res.models)

        res = LeaveOneOut(t, learners, store_models=True)
        self.assertEqual(len(res.models), 50)
        for models in res.models:
            self.assertEqual(len(models), 2)
            self.assertIsInstance(models[0], NaiveBayesModel)
            self.assertIsInstance(models[1], ConstantModel)

    def test_probs(self):
        data = Table('iris')[30:130]
        learners = [MajorityLearner(), MajorityLearner()]

        results = LeaveOneOut(data, learners)

        self.assertEqual(results.predicted.shape, (2, len(data)))
        np.testing.assert_equal(results.predicted, np.ones((2, 100)))
        probs = results.probabilities
        self.assertTrue((probs[:, :, 0] < probs[:, :, 2]).all())
        self.assertTrue((probs[:, :, 2] < probs[:, :, 1]).all())

    def test_miss_majority(self):
        x = np.zeros((50, 3))
        y = x[:, -1]
        x[49] = 1
        data = Table(x, y)
        res = LeaveOneOut(data, [MajorityLearner()])
        np.testing.assert_equal(res.predicted[0][:49], 0)

        x[49] = 0
        res = LeaveOneOut(data, [MajorityLearner()])
        np.testing.assert_equal(res.predicted[0][:49], 0)

        x[25:] = 1
        y = x[:, -1]
        data = Table(x, y)
        res = LeaveOneOut(data, [MajorityLearner()])
        np.testing.assert_equal(res.predicted[0],
                                1 - data.Y[res.row_indices].flatten())

    def test_failed(self):
        self.run_test_failed(LeaveOneOut, 100)

    def test_callback(self):
        self.run_test_callback(LeaveOneOut, np.arange(0, 1.005, 0.01))

    def test_preprocessor(self):
        self.run_test_preprocessor(LeaveOneOut, [149] * 150)


class TestOnTrainingTestCase(unittest.TestCase, CommonSamplingTests):
    def test_results(self):
        nrows, ncols = 50, 10
        t = random_data(nrows, ncols)
        res = TestOnTrainingData(t, [NaiveBayesLearner()])
        y = t.Y
        np.testing.assert_equal(res.actual, y[res.row_indices].reshape(nrows))
        np.testing.assert_equal(res.predicted[0],
                                y[res.row_indices].reshape(nrows))
        np.testing.assert_equal(np.argmax(res.probabilities[0], axis=1),
                                y[res.row_indices].reshape(nrows))
        np.testing.assert_equal(res.row_indices, np.arange(nrows))

    def test_store_data(self):
        nrows, ncols = 50, 10
        t = random_data(nrows, ncols)
        learners = [NaiveBayesLearner()]

        res = TestOnTrainingData(t, learners)
        self.assertIsNone(res.data)

        res = TestOnTrainingData(t, learners, store_data=True)
        self.assertIs(res.data, t)

    def test_store_models(self):
        nrows, ncols = 50, 10
        t = random_data(nrows, ncols)
        learners = [NaiveBayesLearner(), MajorityLearner()]

        res = TestOnTrainingData(t, learners)
        self.assertIsNone(res.models)

        res = TestOnTrainingData(t, learners, store_models=True)
        self.assertEqual(len(res.models), 1)
        for models in res.models:
            self.assertEqual(len(models), 2)
            self.assertIsInstance(models[0], NaiveBayesModel)
            self.assertIsInstance(models[1], ConstantModel)

    def test_probs(self):
        data = Table('iris')[30:130]
        learners = [MajorityLearner(), MajorityLearner()]

        results = TestOnTrainingData(data, learners)

        self.assertEqual(results.predicted.shape, (2, len(data)))
        np.testing.assert_equal(results.predicted, np.ones((2, 100)))
        probs = results.probabilities
        self.assertTrue((probs[:, :, 0] < probs[:, :, 2]).all())
        self.assertTrue((probs[:, :, 2] < probs[:, :, 1]).all())

    def test_miss_majority(self):
        x = np.zeros((50, 3))
        y = x[:, -1]
        x[49] = 1
        data = Table(x, y)
        res = TestOnTrainingData(data, [MajorityLearner()])
        np.testing.assert_equal(res.predicted[0][:49], 0)

        x[49] = 0
        res = TestOnTrainingData(data, [MajorityLearner()])
        np.testing.assert_equal(res.predicted[0][:49], 0)

        x[25:] = 1
        y = x[:, -1]
        data = Table(x, y)
        res = TestOnTrainingData(data, [MajorityLearner()])
        np.testing.assert_equal(res.predicted[0], res.predicted[0][0])

    def test_failed(self):
        self.run_test_failed(TestOnTrainingData, 2)

    def test_callback(self):
        self.run_test_callback(TestOnTrainingData, np.array([0, 0.5, 1]))

    def test_preprocessor(self):
        self.run_test_preprocessor(TestOnTrainingData, [150])


class TestOnTestingTestCase(unittest.TestCase, CommonSamplingTests):
    def test_results(self):
        nrows, ncols = 50, 10
        t = random_data(nrows, ncols)
        res = TestOnTestData(t, t, [NaiveBayesLearner()])
        y = t.Y
        np.testing.assert_equal(res.actual, y[res.row_indices].reshape(nrows))
        np.testing.assert_equal(res.predicted[0],
                                y[res.row_indices].reshape(nrows))
        np.testing.assert_equal(np.argmax(res.probabilities[0], axis=1),
                                y[res.row_indices].reshape(nrows))
        np.testing.assert_equal(res.row_indices, np.arange(nrows))

    def test_probs(self):
        iris = Table('iris')
        data = iris[30:130]
        learners = [MajorityLearner(), MajorityLearner()]
        results = TestOnTestData(data, data, learners)

        self.assertEqual(results.predicted.shape, (2, len(data)))
        np.testing.assert_equal(results.predicted, np.ones((2, 100)))
        probs = results.probabilities
        self.assertTrue((probs[:, :, 0] < probs[:, :, 2]).all())
        self.assertTrue((probs[:, :, 2] < probs[:, :, 1]).all())

        train = iris[50:120]
        test = iris[:50]
        results = TestOnTestData(train, test, learners)
        self.assertEqual(results.predicted.shape, (2, len(test)))
        np.testing.assert_equal(results.predicted, np.ones((2, 50)))
        probs = results.probabilities
        self.assertTrue((probs[:, :, 0] == 0).all())

    def test_store_data(self):
        nrows, ncols = 50, 10
        data = random_data(nrows, ncols)
        train = data[:80]
        test = data[80:]
        learners = [MajorityLearner()]

        res = TestOnTestData(train, test, learners)
        self.assertIsNone(res.data)

        res = TestOnTestData(train, test, learners, store_data=True)
        self.assertIs(res.data, test)

    def test_store_models(self):
        nrows, ncols = 50, 10
        data = random_data(nrows, ncols)
        train = data[:80]
        test = data[80:]
        learners = [NaiveBayesLearner(), MajorityLearner()]

        res = TestOnTestData(train, test, learners)
        self.assertIsNone(res.models)

        res = TestOnTestData(train, test, learners, store_models=True)
        self.assertEqual(len(res.models), 1)
        for models in res.models:
            self.assertEqual(len(models), 2)
            self.assertIsInstance(models[0], NaiveBayesModel)
            self.assertIsInstance(models[1], ConstantModel)

    def test_miss_majority(self):
        x = np.zeros((50, 3))
        y = x[:, -1]
        x[49] = 1
        data = Table(x, y)
        res = TestOnTrainingData(data, [MajorityLearner()])
        np.testing.assert_equal(res.predicted[0][:49], 0)

        x[49] = 0
        res = TestOnTrainingData(data, [MajorityLearner()])
        np.testing.assert_equal(res.predicted[0][:49], 0)

        x[25:] = 1
        y = x[:, -1]
        data = Table(x, y)
        res = TestOnTrainingData(data, [MajorityLearner()])
        np.testing.assert_equal(res.predicted[0], res.predicted[0][0])

    def run_test_failed(self, method, succ_calls):
        # Can't use mocking helpers here (wrong result type for Majority,
        # exception caught for fails)
        def major(*args):
            nonlocal major_call
            major_call += 1
            return MajorityLearner()(*args)

        def fails(_):
            nonlocal fail_calls
            fail_calls += 1
            raise SystemError("failing learner")

        major_call = 0
        fail_calls = 0
        data = random_data(50, 4)
        res = TestOnTestData(data, data, [major, fails, major])
        self.assertFalse(res.failed[0])
        self.assertIsInstance(res.failed[1], Exception)
        self.assertFalse(res.failed[2])
        self.assertEqual(major_call, 2)
        self.assertEqual(fail_calls, 1)

    def test_callback(self):
        def record_progress(p):
            progress.append(p)

        progress = []
        data = random_data(50, 4)
        TestOnTestData(data, data, [MajorityLearner(), MajorityLearner()],
                       callback=record_progress)
        self.assertEqual(progress, [0, 0.5, 1])

    def test_preprocessor(self):
        def preprocessor(data):
            data_sizes.append(len(data))
            return data

        data_sizes = []
        data = random_data(50, 5)
        TestOnTestData(data[:30], data[-20:],
                       [MajorityLearner(), MajorityLearner()],
                       preprocessor=preprocessor)
        self.assertEqual(data_sizes, [30])


class TestTrainTestSplit(unittest.TestCase):
    def test_fixed_training_size(self):
        data = Orange.data.Table("iris")
        train, test = Orange.evaluation.sample(data, 100)
        self.assertEqual(len(train), 100)
        self.assertEqual(len(train) + len(test), len(data))

        train, test = Orange.evaluation.sample(data, 0.1)
        self.assertEqual(len(train), 15)
        self.assertEqual(len(train) + len(test), len(data))

        train, test = Orange.evaluation.sample(data, 0.1, stratified=True)
        self.assertEqual(len(train), 15)
        self.assertEqual(len(train) + len(test), len(data))

        train, test = Orange.evaluation.sample(data, 0.2, replace=True)
        self.assertEqual(len(train), 30)

        train, test = Orange.evaluation.sample(data, 0.9, replace=True)
        self.assertEqual(len(train), 135)
        self.assertGreater(len(train) + len(test), len(data))


class TestShuffleSplit(unittest.TestCase):
    def test_results(self):
        nrows, ncols = 100, 10
        data = random_data(nrows, ncols)
        train_size, n_resamples = 0.6, 10
        res = ShuffleSplit(data, [NaiveBayesLearner()], train_size=train_size,
                           test_size=1 - train_size, n_resamples=n_resamples)
        self.assertEqual(len(res.predicted[0]),
                         n_resamples * nrows * (1 - train_size))

    def test_stratified(self):
        # strata size
        n = 50
        data = Table('iris')

        res = ShuffleSplit(data, [NaiveBayesLearner()], train_size=.5, test_size=.5,
                           n_resamples=3, stratified=True, random_state=0)

        strata_samples = []
        for train, test in res.indices:
            strata_samples.append(np.count_nonzero(train < n) == n/2)
            strata_samples.append(np.count_nonzero(train < 2 * n) == n)

        self.assertTrue(all(strata_samples))

    def test_not_stratified(self):
        # strata size
        n = 50
        data = Table('iris')

        res = ShuffleSplit(data, [NaiveBayesLearner()], train_size=.5, test_size=.5,
                           n_resamples=3, stratified=False, random_state=0)

        strata_samples = []
        for train, test in res.indices:
            strata_samples.append(np.count_nonzero(train < n) == n/2)
            strata_samples.append(np.count_nonzero(train < 2 * n) == n)

        self.assertTrue(not all(strata_samples))


class TestAugmentedData(unittest.TestCase):
    def test_augmented_data_classification(self):
        data = Table("iris")
        n_classes = len(data.domain.class_var.values)
        res = CrossValidation(data, [NaiveBayesLearner()], store_data=True)
        table = res.get_augmented_data(['Naive Bayes'])

        self.assertEqual(len(table), len(data))
        self.assertEqual(len(table.domain.attributes), len(data.domain.attributes))
        self.assertEqual(len(table.domain.class_vars), len(data.domain.class_vars))
        # +1 for class, +n_classes for probabilities, +1 for fold
        self.assertEqual(len(table.domain.metas), len(data.domain.metas) + 1 + n_classes + 1)
        self.assertEqual(table.domain.metas[len(data.domain.metas)].values, data.domain.class_var.values)

        res = CrossValidation(data, [NaiveBayesLearner(), MajorityLearner()], store_data=True)
        table = res.get_augmented_data(['Naive Bayes', 'Majority'])

        self.assertEqual(len(table), len(data))
        self.assertEqual(len(table.domain.attributes), len(data.domain.attributes))
        self.assertEqual(len(table.domain.class_vars), len(data.domain.class_vars))
        self.assertEqual(len(table.domain.metas), len(data.domain.metas) + 2*(n_classes+1) + 1)
        self.assertEqual(table.domain.metas[len(data.domain.metas)].values, data.domain.class_var.values)
        self.assertEqual(table.domain.metas[len(data.domain.metas)+1].values, data.domain.class_var.values)

    def test_augmented_data_regression(self):
        data = Table("housing")
        res = CrossValidation(data, [LinearRegressionLearner(), ], store_data=True)
        table = res.get_augmented_data(['Linear Regression'])

        self.assertEqual(len(table), len(data))
        self.assertEqual(len(table.domain.attributes), len(data.domain.attributes))
        self.assertEqual(len(table.domain.class_vars), len(data.domain.class_vars))
        # +1 for class, +1 for fold
        self.assertEqual(len(table.domain.metas), len(data.domain.metas) + 1 + 1)

        res = CrossValidation(data, [LinearRegressionLearner(), MeanLearner()], store_data=True)
        table = res.get_augmented_data(['Linear Regression', 'Mean Learner'])

        self.assertEqual(len(table), len(data))
        self.assertEqual(len(table.domain.attributes), len(data.domain.attributes))
        self.assertEqual(len(table.domain.class_vars), len(data.domain.class_vars))
        # +2 for class, +1 for fold
        self.assertEqual(len(table.domain.metas), len(data.domain.metas) + 2 + 1)
