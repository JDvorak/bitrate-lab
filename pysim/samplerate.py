# Colleen Josephson, 2013
# This file attempts to implement the SampleRate bit rate selection algorithm 
# as outlined in the JBicket MS Thesis.

from __future__ import division

import random
import common
import collections
from common import ieee80211_to_idx

# Constants: send 1500 bytes at a time, with 1 try each in the MRR
NBYTES = 1500
NRETRIES = 1

npkts = 0 # number of packets sent over link
nsuccess = 0 #number of packets sent successfully 

# The average back-off period, in microseconds, for up to 8 attempts
# of a 802.11b unicast packet.
# TODO: find g data
backoff = [0, 155, 315, 635, 1275, 2555, 5115]

#"To calculate the transmission time of a n-byte unicast packet given
# the bit-rate b and number of retries r, SampleRate uses the
# following equation based on the 802.11 unicast retransmission
# mechanism detailed in Section 2.2"

def tx_time(rix, retries, nbytes):
    # tx_time(b, r, n) = difs + backoff[r] + \
    #                  + (r + 1)*(sifs + ack + header + (n * 8/b)

    #"where difs is 50 microseconds in 802.11b and 28 microseconds in
    # 802.11a/g, sifs is 10 microseconds for 802.11b and 9 for
    # 802.11a/g, and ack is 304 microseconds using 1 megabit
    # acknowledgments for 802.11b and 200 microseconds for 6 megabit
    # acknowledgments.  header is 192 microseconds for 1 megabit
    # 802.11b packets, 96 for other 802.11b bit-rates, and 20 for
    # 802.11a/g bit-rates. backoff(r) is calculated using the table"

    rate = common.RATES[rix]
    version = "g" if rate.phy == "ofdm" else "b"

    difs = 50 if version == "b" else 28
    sifs = 10 if version == "b" else 9
    ack = 304 # Somehow 6mb acks aren't used
    header = 192 if rate.code == 0 else 96 if version == "b" else 20

    backoff_r = backoff[retries] if retries < len(backoff) else backoff[-1]

    return difs + backoff_r + \
        (retries + 1) * (sifs + ack + header + (nbytes * 8 / rate.mbps))

Packet = collections.namedtuple("Packet", ["time_sent", "success",
                                           "txTime", "rate"])

class Rate:
    def __init__(self, rate):
        self.rate = rate #in mbps
        self.idx = ieee80211_to_idx(rate)
        self.success = 0
        self.tries = 0
        self.pktAcked = 0
        self.succFails = 0
        self.totalTX = 0
        self.avgTX = float("inf")
        #pktsize/channelrate. pktsize = 1500 bytes
        self.losslessTX = tx_time(self.idx, 0, 1500) #microseconds
        self.window = [] #packets rcvd in last 10s


# The modulation scheme used in 802.11g is orthogonal
# frequency-division multiplexing (OFDM) copied from 802.11a with data
# rates of 6, 9, 12, 18, 24, 36, 48, and 54 Mbit/s, and reverts to CCK
# (like the 802.11b standard) for 5.5 and 11 Mbit/s and
# DBPSK/DQPSK+DSSS for 1 and 2 Mbit/s.  Even though 802.11g operates
# in the same frequency band as 802.11b, it can achieve higher data
# rates because of its heritage to 802.11a.
rates = dict((r, Rate(r)) for r in [1, 2, 5.5, 6, 9, 11, 12, 18, 24, 36, 48, 54])
currRate = rates[54] #current best bitRate

#multi-rate retry returns an array of (rate, ntries) for the next n packets
def apply_rate(cur_time):
    global currRate, npkts, nsuccess
    remove_stale_results(cur_time)
    
    #"Increment the number of packets sent over the link"
    npkts += 1
    
    #"If no packets have been successfully acknowledged, return the
    # highest bit-rate that has not had 4 successive failures."
    if nsuccess == 0:
        for i, r in sorted(rates.items(), reverse=True):
            if r.succFails < 4:
                currRate = r
                return [(r.idx, NRETRIES)]

    # Every 10 packets, select a random non-failing bit rate w/ better avg tx
    #"If the number of packets sent over the link is a multiple of ten,"
    if (nsuccess != 0) and (npkts%10 == 0):
        #"select a random bit-rate from the bit-rates"
        cavgTX = rates[currRate.rate].avgTX

        #"that have not failed four successive times and that have a
        # minimum packet transmission time lower than the current
        # bit-rate's average transmission time."
        eligible = [r for i, r in rates.items()
                    if r.losslessTX < cavgTX and r.succFails < 4]

        if len(eligible) > 0:
            sampleRate = random.choice(eligible)
            return [(sampleRate.idx, NRETRIES)]

    #"Otherwise, send packet at the bit-rate that has the lowest avg
    # transmission time" Trusts that currRate is properly maintained
    # to be lowest avgTX
    return [(currRate.idx, NRETRIES)]


#"When process f eedback() runs, it updates information that tracks
# the number of samples and recalculates the average transmission time
# for the bit-rate and destination. process_feedback() performs the
# following operations:"
def process_feedback(status, timestamp, delay, tries):
    #status: true if packet was rcvd successfully
    #timestamp: time pkt was sent
    #delay: rtt for entire process (inluding multiple tries) in nanoseconds
    #tries: an array of (bitrate, nretries) 
    global currRate, npkts, nsuccess, NBYTES
    (bitrate, nretries) = tries[0]
    nretries -= 1
    bitrate = common.RATES[bitrate].mbps

    #"Calculate the transmission time for the packet based on the
    # bit-rate and number of retries using Equation 5.1 below."

    tx = tx_time(tries[0][0], nretries, NBYTES)

    #"Look up the destination and add the transmission time to the
    # total transmission times for the bit-rate."
    
    br = rates[bitrate]

    if not status:
        br.succFails += 1
        #"If the packet failed, increment the number of successive
        # failures for the bit-rate.
    else:
        #"Otherwise reset it."
        br.succFails = 0

        #"If the packet succeeded, increment the number of successful
        # packets sent at that bit-rate.
        br.success += 1
        nsuccess += 1

    #"Re-calculate the average transmission time for the bit-rate
    # based on the sum of trans- mission times and the number of
    # successful packets sent at that bit-rate."

    br.totalTX += tx

    if br.success == 0:
        br.avgTX = float("inf")
    else:
        br.avgTX = br.totalTX/br.success

    #"Set the current-bit rate for the destination to the one with the
    # minimum average transmission time."
    calculateMin()
    
    #"Append the current time, packet status, transmission time, and
    # bit-rate to the list of transmission results."
    p = Packet(timestamp, status, tx, bitrate)
    br.window.append(p)

#"SampleRate's remove stale results() function removes results from
# the transmission results queue that were obtained longer than ten
# seconds ago."
def remove_stale_results(cur_time):
    window_cutoff = cur_time - 1e10 #window size of 10s

    
    for r in rates.values():
        for p in r.window:
            #"For each stale transmission result, it does the following"
            if p.time_sent < window_cutoff:
                #"Remove the transmission time from the total
                # transmission times at that bit-rate to that
                # destination."
                r.window.remove(p)
                r.totalTX -= p.txTime

                #"If the packet succeeded, decrement the number of
                # successful packets at that bit-rate to that
                # destination."
                if p.success:
                    r.success -= 1
        #"After remove stale results() performs these operations for
        #each stale sample, it recalculates the minimum average
        #transmission times for each bit-rate and destination.
        if r.success == 0:
            r.avgTX = float("inf")
        else:
            r.avgTX = r.totalTX/r.success

    for r in rates.values():
        succFails = 0
        maxSuccFails = 0

        for p in r.window:
            if p.success:
                if succFails > maxSuccFails:
                    maxSuccFails = succFails
                succFails = 0
            else:
                succFails += 1
        if succFails > maxSuccFails:
            maxSuccFails = succFails

        r.succFails = maxSuccFails
                
    
    #"remove_stale_results() then sets the current bit-rate for each
    # destination to the one with the smallest average trans- mission
    # time."
    calculateMin()
        

def calculateMin():
    global currRate, npkts, nsuccess

    #set current rate to the one w/ min avg tx time
    c = rates[currRate.rate]
    if c.succFails > 4:
        c.avgTX = float("inf")
        #c = rates[1]

    for i, r in sorted(rates.items(), reverse=True):
        if r.rate < c.rate and r.avgTX == float("inf") \
           and r.succFails == 0 and r.losslessTX < c.avgTX:
            c = r
            break
        if c.avgTX > r.avgTX and r.succFails < 4:
            c = r

    currRate = c
