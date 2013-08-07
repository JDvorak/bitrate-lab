import os
import rates

RATE=float(os.environ["RATE"]) if "RATE" in os.environ else 1

# Read the rate as a Mbps value and convert it to an index
try:
    IDX = [i for i, r in enumerate(rates.RATES) if r.mbps == RATE][0]
except ValueError:
    opts = [str(rate.mbps) for rate in rates.RATES]
    print("Invalid rate.  Options are: {}".format(", ".join(opts)))
    exit()
else:
    print("Running at rate %r Mbps..." % RATE)

def apply_rate(time):
    return [(IDX, 4)] * 4

def process_feedback(status, timestamp, delay, tries):
    pass
