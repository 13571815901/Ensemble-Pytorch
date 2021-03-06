"""
  In fusion-based ensemble methods, the predictions from all base estimators
  are first aggregated as an average output. After then, the training loss is
  computed based on this average output and the ground-truth. The training loss
  is then back-propagated to all base estimators simultaneously.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

from ._base import BaseModule
from . import utils


class FusionClassifier(BaseModule):
    """Implementation of the FusionClassifier."""

    def _forward(self, X):
        """
        Implementation on the internal data forwarding in FusionClassifier.
        """
        batch_size = X.size()[0]
        proba = torch.zeros(batch_size, self.n_outputs).to(self.device)

        # Take the average over predictions from all base estimators.
        for estimator in self.estimators_:
            proba += estimator(X) / self.n_estimators

        return proba

    def forward(self, X):
        """
        Implementation on the data forwarding in FusionClassifier.

        Parameters
        ----------
        X : tensor
            Input batch of data, which should be a valid input data batch for
            base estimators.

        Returns
        -------
        proba : tensor of shape (batch_size, n_classes)
            The predicted class distribution.
        """
        proba = self._forward(X)

        return F.softmax(proba, dim=1)

    def fit(self,
            train_loader,
            lr=1e-3,
            weight_decay=5e-4,
            epochs=100,
            optimizer="Adam",
            log_interval=100):
        """
        Implementation on the training stage of FusionClassifier.

        Parameters
        ----------
        train_loader : torch.utils.data.DataLoader
            A :mod:`DataLoader` container that contains the training data.
        lr : float, default=1e-3
            The learning rate of the parameter optimizer.
        weight_decay : float, default=5e-4
            The weight decay of the parameter optimizer.
        epochs : int, default=100
            The number of training epochs.
        optimizer : {"SGD", "Adam", "RMSprop"}, default="Adam"
            The type of parameter optimizer.
        log_interval : int, default=100
            The number of batches to wait before printting the training status.
        """
        
        # Instantiate base estimators and set attributes
        for _ in range(self.n_estimators):
            self.estimators_.append(self._make_estimator())
        self.n_outputs = self._decide_n_outputs(train_loader, True)
        optimizer = utils.set_optimizer(self, optimizer, lr, weight_decay)

        self.train()
        self._validate_parameters(lr, weight_decay, epochs, log_interval)
        criterion = nn.CrossEntropyLoss()

        # Training loop
        for epoch in range(epochs):
            for batch_idx, (data, target) in enumerate(train_loader):

                batch_size = data.size()[0]
                data, target = data.to(self.device), target.to(self.device)

                output = self._forward(data)
                loss = criterion(output, target)

                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

                # Print training status
                if batch_idx % log_interval == 0:
                    pred = output.data.max(1)[1]
                    correct = pred.eq(target.view(-1).data).sum()

                    msg = ("Epoch: {:03d} | Batch: {:03d} | Loss: {:.5f} |"
                           " Correct: {:d}/{:d}")
                    print(msg.format(epoch, batch_idx, loss,
                                     correct, batch_size))

    def predict(self, test_loader):
        """
        Implementation on the evaluating stage of FusionClassifier.

        Parameters
        ----------
        test_loader : torch.utils.data.DataLoader
            A :mod:`DataLoader` container that contains the testing data.

        Returns
        -------
        accuracy : float
            The testing accuracy of the fitted model on the ``test_loader``.
        """
        self.eval()
        correct = 0.

        for batch_idx, (data, target) in enumerate(test_loader):
            data, target = data.to(self.device), target.to(self.device)
            output = self.forward(data)
            pred = output.data.max(1)[1]
            correct += pred.eq(target.view(-1).data).sum()

        accuracy = 100. * float(correct) / len(test_loader.dataset)

        return accuracy


class FusionRegressor(BaseModule):
    """Implementation of the FusionRegressor."""

    def forward(self, X):
        """
        Implementation on the data forwarding process in FusionRegressor.

        Parameters
        ----------
        X : tensor
            Input tensor. Internally, the model will check whether ``X`` is
            compatible with the base estimator.

        Returns
        -------
        pred : tensor of shape (batch_size, n_outputs)
            The predicted values.
        """
        batch_size = X.size()[0]
        pred = torch.zeros(batch_size, self.n_outputs).to(self.device)

        # Take the average over predictions from all base estimators.
        for estimator in self.estimators_:
            pred += estimator(X) / self.n_estimators

        return pred

    def fit(self,
            train_loader,
            lr=1e-3,
            weight_decay=5e-4,
            epochs=100,
            optimizer="Adam",
            log_interval=100):
        """
        Implementation on the training stage of FusionRegressor.

        Parameters
        ----------
        train_loader : torch.utils.data.DataLoader
            A :mod:`DataLoader` container that contains the training data.
        lr : float, default=1e-3
            The learning rate of the parameter optimizer.
        weight_decay : float, default=5e-4
            The weight decay of the parameter optimizer.
        epochs : int, default=100
            The number of training epochs.
        optimizer : {"SGD", "Adam", "RMSprop"}, default="Adam"
            The type of parameter optimizer.
        log_interval : int, default=100
            The number of batches to wait before printting the training status.
        """
        # Instantiate base estimators and set attributes
        for _ in range(self.n_estimators):
            self.estimators_.append(self._make_estimator())
        self.n_outputs = self._decide_n_outputs(train_loader, False)
        optimizer = utils.set_optimizer(self, optimizer, lr, weight_decay)

        self.train()
        self._validate_parameters(lr, weight_decay, epochs, log_interval)
        criterion = nn.MSELoss()

        # Training loop
        for epoch in range(epochs):
            for batch_idx, (data, target) in enumerate(train_loader):

                data, target = data.to(self.device), target.to(self.device)

                output = self.forward(data)
                loss = criterion(output, target)

                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

                # Print training status
                if batch_idx % log_interval == 0:
                    msg = 'Epoch: {:03d} | Batch: {:03d} | Loss: {:.5f}'
                    print(msg.format(epoch, batch_idx, loss))

    def predict(self, test_loader):
        """
        Implementation on the evaluating stage of FusionRegressor.

        Parameters
        ----------
        test_loader : torch.utils.data.DataLoader
            A :mod:`DataLoader` container that contains the testing data.
        
        Returns
        -------
        mse : float
            The testing mean squared error of the fitted model on the
            ``test_loader``.
        """
        self.eval()
        mse = 0.
        criterion = nn.MSELoss()

        for batch_idx, (data, target) in enumerate(test_loader):
            data, target = data.to(self.device), target.to(self.device)
            output = self.forward(data)

            mse += criterion(output, target)

        return mse / len(test_loader)
