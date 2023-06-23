"""The SampleChecker class and it's implementations."""

from abc import ABC, abstractmethod
import time
from collections import deque

from scenic.core.requirements import IntersectionRequirement, BlanketCollisionRequirement

class SampleChecker(ABC):
    def __init__(self):
        self.requirements = None

    def setRequirements(self, requirements):
        assert self.requirements is None
        self.requirements = tuple(requirements)

    @abstractmethod
    def checkRequirementsInner(self, sample):
        pass

    def checkRequirements(self, sample):
        assert self.requirements is not None
        return self.checkRequirementsInner(sample)

class BasicChecker(SampleChecker):
    """ Basic requirement checker.
    
    Evaluates requirements in order, with a tiny bit of tuning.
    """
    def __init__(self, initialCollisionCheck):
        super().__init__()
        self.initialCollisionCheck = initialCollisionCheck

    def setRequirements(self, requirements):
        target_reqs = []
        for req in requirements:
            if req.optional:
                # Basic checker ignores optional requirements unless otherwise noted.
                if (isinstance(req, BlanketCollisionRequirement)
                   and self.initialCollisionCheck
                   and sum(isinstance(r, IntersectionRequirement) for r in requirements) >= 3):
                    target_reqs.append(req)
            else:
                target_reqs.append(req)

        super().setRequirements(target_reqs)

    def checkRequirementsInner(self, sample):
        for req in self.requirements:
            if req.active and req.falsifiedBy(sample):
                return req.violationMsg

        return None

class WeightedAcceptanceChecker(SampleChecker):
    """ Picks the requirement with the lowest time-weighted acceptance chance.

    Incentivizes exploration by initializing all buffer values to 0.

    Args:
        bufferSize: Max samples to use when calculating time-weighted
            rejection chance.
    """
    def __init__(self, bufferSize=10):
        super().__init__()
        self.bufferSize = bufferSize

    def setRequirements(self, requirements):
        super().setRequirements(requirements)

        self.buffers = {req: deque(maxlen=self.bufferSize) for req in self.requirements}
        for req in self.requirements:
            self.buffers[req].extend([(0,0)]*self.bufferSize)

    def checkRequirementsInner(self, sample):
        for req in self.sortedRequirements():
            # Evaluate the requirement with timing info.
            start = time.perf_counter()
            rejected = req.falsifiedBy(sample)
            # Create metrics (Accepted, Time Taken)
            metrics = (int(not rejected), time.perf_counter()-start)

            self.updateMetrics(req, metrics)

            if rejected:
                return req.violationMsg

        return None

    def sortedRequirements(self):
        """ Return the list of requirements in sorted order"""
        # Extract and sort active requirements
        reqs = [req for req in self.requirements if req.active]
        reqs.sort(key=self.getWeightedAcceptanceProb)

        # Remove any optional requirements at the end of the list, since they're useless
        while reqs and reqs[-1].optional:
            reqs.pop()

        return reqs

    def updateMetrics(self, req, metrics):
        """ Update the metrics for a given requirement"""
        target_buffer = self.buffers[req]
        target_buffer.appendleft(metrics)

    def getWeightedAcceptanceProb(self, req):
        target_buffer = self.buffers[req]
        mean_accept = sum(metric[0] for metric in target_buffer)/self.bufferSize
        mean_time = sum(metric[1] for metric in target_buffer)/self.bufferSize
        return mean_accept * mean_time
