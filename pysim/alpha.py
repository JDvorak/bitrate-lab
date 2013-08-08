from constant import BitrateAlgorithm, initialize
import random
import bits

EWMA_LEVEL = .75
def ewma(old, new, weight):
    beta = EWMA_LEVEL / (1 - EWMA_LEVEL)
    return (old * beta + new * weight) / (beta + weight)

class Alpha(BitrateAlgorithm):
    class Rate(BitrateAlgorithm.Rate):
        def __init__(self, rix, info):
            BitrateAlgorithm.Rate.__init__(self, rix, info)
            self.probability = 1.0
            self.samplerate = 3e8 # As per Minstrel
            self.decayrate  = 10 * self.tx_lossless() # Per millisecond
            
            # Time of next sample
            self.next_sample = None
            self.last_sample = None
            self.last_actual = None

        def report_sample(self, time, status):
            timespan = time - self.last_sample
            self.next_sample = time + (random.random() + .5) * self.samplerate
            self.last_sample = time

            self.probability = ewma(self.probability, 1.0 if status else 0.0,
                                    timespan / self.samplerate)

        def init(self, time):
            self.next_sample = time + (random.random() + .5) * self.samplerate
            self.last_sample = time
            self.last_actual = time

        def report_actual(self, time, status):
            timespan = time - self.last_actual
            self.probability = ewma(self.probability, 1 if status else 0,
                                    timespan / self.decayrate)
            self.last_actual = time

        def tx_lossless(self, nbytes=1500):
            return bits.tx_lossless(self.idx, nbytes)

        def tx_time(self, nbytes=1500):
            return bits.tx_time(self.idx, self.probability, nbytes)

    def __init__(self):
        BitrateAlgorithm.__init__(self)
        self.was_sample = False
        self.last_rate = None
        self.inited = False


    def apply_rate(self, timestamp):
        if not self.inited:
            for r in self.RATES: r.init(timestamp)
            self.inited = True
        samplable_rates = [rate for rate in self.RATES
                           if rate.next_sample is None
                           or rate.next_sample < timestamp]

        if samplable_rates:
            self.was_sample = True
            rate = random.choice(samplable_rates)
        else:
            self.was_sample = False
            rate = min(self.RATES, key=self.Rate.tx_time)
            if rate != self.last_rate:
                self.switch_rate(self.last_rate, rate)

        return [(rate.idx, 1)]

    def switch_rate(self, old, new):
        self.last_rate = new

    def process_feedback(self, status, timestamp, delay, tries):
        rix, _ = tries[0]
        rate = self.RATES[rix]

        if self.was_sample:
            rate.report_sample(timestamp, status)
        else:
            rate.report_actual(timestamp, status)

apply_rate, process_feedback = initialize(Alpha)