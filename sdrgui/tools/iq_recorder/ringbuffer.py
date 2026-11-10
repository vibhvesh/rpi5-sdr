"""A sample-count ring buffer of complex IQ for pre-trigger capture."""
import numpy as np

class IqRing:
    def __init__(self, max_samples):
        self.max_samples = max(0, int(max_samples))
        self._chunks = []
        self._n = 0

    def clear(self):
        self._chunks.clear()
        self._n = 0

    def push(self, iq):
        if self.max_samples <= 0:
            return
        x = np.asarray(iq)
        if x.size == 0:
            return
        self._chunks.append(x.copy())
        self._n += x.size
        while self._n > self.max_samples and self._chunks:
            extra = self._n - self.max_samples
            first = self._chunks[0]
            if first.size <= extra:
                self._chunks.pop(0)
                self._n -= first.size
            else:
                self._chunks[0] = first[extra:]
                self._n -= extra
                break

    def snapshot(self):
        if not self._chunks:
            return np.zeros(0, dtype=np.complex64)
        return np.concatenate(self._chunks)

    def __len__(self):
        return self._n
