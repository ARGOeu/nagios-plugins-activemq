import time

class Timer(object):
    
    def __init__(self, timeout=None):
        self._stopTime = None
        self._timeout = timeout
        self._startTime = self.time()
  
    def stop(self):
        self._stopTime = self.last()
        return self.elapsed

    def elapsed(self):
        return self.last() - self.startTime
    
    def left(self):
        return max(0, self._timeout - self.elapsed)
    
    def sleep(self, amount):
        if amount < self.left:
            time.sleep(amount)
        else:
            time.sleep(self.left)
    
    def startTime(self):
        return self._startTime
    
    def stopTime(self):
        return self._stopTime
    
    def last(self):
        if self._stopTime:
            return self._stopTime
        return self.time()
    
    def time(self):
        return time.time()
    
    def __str__(self):
        return '%.2fs' % (self.elapsed)
    
    startTime = property(startTime)
    stopTime = property(stopTime)
    elapsed = property(elapsed)
    left = property(left)
