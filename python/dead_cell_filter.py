import findpeaks
import numpy as np
from scipy.stats.mstats import mquantiles as quantile
import matplotlib.pyplot as plt
# from itertools import compress
import smooth
from scipy.stats import gaussian_kde

#  Gating based on LDR
#  --------------------
# mx = np.max(ldrtxt.tolist())+0.01
# x_ldr = np.arange(-0.01, mx, 0.0002)


def get_ldrgates(ldrtxt, x_ldr=None):
    if x_ldr is None:
        mx = np.max(ldrtxt.tolist())+0.01
        x_ldr = np.arange(-0.01, mx, 0.0002)
    f_ldr = findpeaks.get_kde(ldrtxt, x_ldr)  # ldrtxt should be an array
    peak_amp, peak_loc, peak_width = findpeaks.findpeaks(
        f_ldr.tolist(), npeaks=1)

    # Find location of minimun on the right
    f_neg = [-x for x in f_ldr[peak_loc[0]:]]
    _, trough_loc, _ = findpeaks.findpeaks(f_neg, npeaks=1)
    trough_loc = trough_loc[0] + peak_loc[0] - 1

    # choose LDR cutoff based on half-proximal width and right trough of peak
    ldrwidth_5x = peak_loc + (5 * peak_width[0])
    ldrwdith_2p5 = peak_loc + (2.5 * peak_width[0])
    cutoff_index_1 = len(x_ldr) - 2
    cutoff_index_2 = np.max([3,
                             np.min([trough_loc, ldrwidth_5x]),
                             ldrwdith_2p5])

    ldr_cutoff = x_ldr[np.min([cutoff_index_1, int(cutoff_index_2)])]

    ldr_gates = [-np.inf, ldr_cutoff]
    return ldr_gates


def get_ldrlims(ldrtxt, x_ldr=None):
    if x_ldr is None:
        mx = np.max(ldrtxt.tolist())+0.01
        x_ldr = np.arange(-0.01, mx, 0.0002)
    ldr_lims = (quantile(ldrtxt, [5e-3, 0.995]) +
                [(2.5 * (x_ldr[1] - x_ldr[0])) * x for x in [-1, 1]])
    return ldr_lims


def plot_ldr_gating(ldrtxt, x_ldr=None, ldr_gates=None, ldr_lims=None):
    if x_ldr is None:
        mx = np.max(ldrtxt.tolist())+0.01
        x_ldr = np.arange(-0.01, mx, 0.0002)
    f_ldr = findpeaks.get_kde(ldrtxt, x_ldr)
    if not ldr_gates:
        ldr_gates = get_ldrgates(ldrtxt, x_ldr)
    if not ldr_lims:
        ldr_lims = get_ldrlims(ldrtxt, x_ldr)
    log_frac = np.log10(f_ldr+np.max(f_ldr)/100) - np.log10(np.max(f_ldr)/100)
    plt.plot(x_ldr, log_frac)

    x_vals = [ldr_gates[1],
              np.max([ldr_gates[0], np.min(x_ldr)]),
              np.max([ldr_gates[0], np.min(x_ldr)]),
              ldr_gates[1], ldr_gates[1]]
    y_vals = [np.log10(np.max(f_ldr)) * y for y in [0, 0, 0.5, 0.5, 0]]
    plt.plot(x_vals, y_vals, 'r')
    plt.xlim(ldr_lims)
    f_ldr_max = np.log10(np.max(f_ldr)) - np.log10(np.max(f_ldr)/100) + 0.1
    plt.ylim([0, f_ldr_max])
    plt.xlabel('LDRtxt intensity')
    plt.ylabel('kernel density estimate')
    return ldr_gates, ldr_lims

# Gating based on DNA content
# ---------------------------
# x_dna = np.arange(2.5, 8, 0.02)


def compute_log_dna(dna, x_dna=None):
    if x_dna is None:
        x_dna = np.arange(2.5, 8, 0.02)
    dna_upper_bound = 10 ** x_dna[-3]
    dna_lower_bound = 10 ** x_dna[2]
    dna_upper_bounded = [d if d < dna_upper_bound else dna_upper_bound
                         for d in dna]
    dna_bounded = [d if d > dna_lower_bound else dna_lower_bound
                   for d in dna in dna_upper_bounded]
    log_dna = np.array([np.log10(d) for d in dna_bounded])
    return log_dna


def get_g1_location(log_dna, x_dna, ldrtxt, ldr_gates):
    if x_dna is None:
        x_dna = np.arange(2.5, 8, 0.02)
    # Only consider susbet of cells with LDR within ldr_gates
    log_dna_low_ldr = log_dna[(ldr_gates[1] >= ldrtxt) &
                              (ldrtxt >= ldr_gates[0])]
    f_dna_low_ldr = findpeaks.get_kde(log_dna_low_ldr, x_dna)
    dna_peaks_amp, dna_peaks_loc, = findpeaks.findpeaks(f_dna_low_ldr.tolist())
    # Remove lesser peaks
    dna_peaks_loc = dna_peaks_loc[dna_peaks_amp > np.max(dna_peaks_amp/10)]
    dna_peaks_amp = dna_peaks_amp[dna_peaks_amp > np.max(dna_peaks_amp/10)]
    xdna_loc = x_dna[dna_peaks_loc[:4]]  # take the 4 highest peaks
    # compute dna density surrounding peaks
    dna_density = [np.mean(np.array(log_dna > (x - 0.2 * np.log10(2))) &
                           np.array(log_dna < (x + 1.2 * np.log10(2))))
                   for x in xdna_loc] + dna_peaks_amp
    # Find G1 peak
    if len(xdna_loc) == 2:
        g1_loc = np.min(xdna_loc)
    else:
        g1_loc = xdna_loc[np.argmax(dna_density)]
    return g1_loc


def get_g2_location(log_dna, x_dna, ldrtxt, ldr_gates, g1_loc):
    # Get G2 peak and location
    # Only consider subset of cells witt LDR internsity within ldr_gates and
    # DNA content > (g1_loc + 0.4 * log10(2))
    if x_dna is None:
        x_dna = np.arange(2.5, 8, 0.02)
    log_dna_g2_range = log_dna[(log_dna > (g1_loc + 0.4 * np.log10(2))) &
                               (ldr_gates[1] >= ldrtxt) &
                               (ldrtxt >= ldr_gates[0])]
    f_dna_g2_range = findpeaks.get_kde(log_dna_g2_range, x_dna)
    f_smooth = smooth.smooth(f_dna_g2_range, 5, 'flat')
    peak_amp, peak_loc, _ = findpeaks.findpeaks(f_smooth.tolist())
    peak_loc = peak_loc[peak_amp > np.max(peak_amp/10)]
    xdna_loc = x_dna[peak_loc]
    xdna_loc = xdna_loc[xdna_loc > (g1_loc + 0.5 * np.log10(2))]
    if len(xdna_loc) > 1:
        g2_loc = xdna_loc[np.argmin(
            np.abs((xdna_loc - (g1_loc + np.log10(2))))
        )]
    elif len(xdna_loc) == 1:
        g2_loc = xdna_loc[0]
    else:
        g2_loc = g1_loc + np.log10(2)
    return g2_loc


def get_g1_g2_position(log_dna, x_dna, ldrtxt, ldr_gates):
    if x_dna is None:
        x_dna = np.arange(2.5, 8, 0.02)
    g1_loc = get_g1_location(log_dna, x_dna, ldrtxt, ldr_gates)
    g2_loc = get_g2_location(log_dna, x_dna, ldrtxt, ldr_gates, g1_loc)
    g1_g2_pos = [g1_loc, g2_loc]
    return g1_g2_pos


def get_dnalims(log_dna, x_dna=None):
    if x_dna is None:
        x_dna = np.arange(2.5, 8, 0.02)
    dna_lims = (quantile(log_dna, [5e-3, 0.995]) +
                [(2.5 * (x_dna[1] - x_dna[0])) * x for x in [-1, 1]])
    return dna_lims


def plot_dna_gating(dna, ldrtxt, ldr_gates, x_dna=None):
    if x_dna is None:
        x_dna = np.arange(2.5, 8, 0.02)
    log_dna = compute_log_dna(dna, x_dna)
    f_dna = findpeaks.get_kde(np.array(log_dna), x_dna)
    plt.plot(x_dna, f_dna, '-k')

    log_dna_low_ldr = log_dna[(ldr_gates[1] >= ldrtxt) &
                              (ldrtxt >= ldr_gates[0])]
    f_dna_low_ldr = findpeaks.get_kde(log_dna_low_ldr, x_dna)
    plt.plot(x_dna, f_dna_low_ldr, '--r')

    g1_loc = get_g1_location(log_dna, x_dna, ldrtxt, ldr_gates)
    log_dna_g2_range = log_dna[(log_dna > (g1_loc + 0.4 * np.log10(2))) &
                               (ldr_gates[1] >= ldrtxt) &
                               (ldrtxt >= ldr_gates[0])]
    f_dna_g2_range = findpeaks.get_kde(log_dna_g2_range, x_dna)
    plt.plot(x_dna, f_dna_g2_range, ':')

    g1_g2_pos = get_g1_g2_position(log_dna, x_dna, ldrtxt, ldr_gates)
    g1_loc = g1_g2_pos[0]
    g2_loc = g1_g2_pos[1]
    dna_gates = [a + b for a, b in zip(
        [g1_g2_pos[i] for i in [0, 0, 1, 1]],
        [(g2_loc-g1_loc) * s for s in [-1.5, -.9, 1.3, 2.2]]
    )]

    y_vals = [np.max(f_dna) * y for y in [0, 1.02, 1.02, 0]]
    inner_x_vals = [dna_gates[i] for i in [1, 1, 2, 2]]
    outer_x_vals = [dna_gates[i] for i in [0, 0, 3, 3]]
    plt.plot(inner_x_vals, y_vals, '-r', linewidth=2)
    plt.plot(outer_x_vals, y_vals, '-r')
    dna_lims = get_dnalims(log_dna, x_dna)
    dna_lims = [np.min((dna_lims[0], dna_gates[0]-0.1)),
                np.max((dna_lims[1], dna_gates[3]+0.1))]
    plt.xlabel('log10 (DNA)')
    plt.ylabel('kernel density estimate')
    plt.xlim(dna_lims)
    return dna_gates


def plot_ldr_dna_scatter(dna, ldrtxt, x_dna=None, x_ldr=None):
    if x_dna is None:
        x_dna = np.arange(2.5, 8, 0.02)
    if x_ldr is None:
        mx = np.max(ldrtxt.tolist())+0.01
        x_ldr = np.arange(-0.01, mx, 0.0002)
    log_dna = compute_log_dna(dna, x_dna)
    xy = np.vstack([log_dna, ldrtxt])
    z = gaussian_kde(xy)(xy)
    plt.scatter(log_dna, ldrtxt, c=z, s=10)

    ldr_gates = get_ldrgates(ldrtxt, x_ldr)
    print(ldr_gates)
    g1_g2_pos = get_g1_g2_position(log_dna, x_dna, ldrtxt, ldr_gates)
    g1_loc = g1_g2_pos[0]
    g2_loc = g1_g2_pos[1]
    dna_gates = [a + b for a, b in zip(
        [g1_g2_pos[i] for i in [0, 0, 1, 1]],
        [(g2_loc-g1_loc) * s for s in [-1.5, -.9, 1.3, 2.2]])]
    ldr_gates = [0 if lg < 0 else lg for lg in ldr_gates]
    plt.plot([dna_gates[i] for i in [0, 0, 3, 3, 0]],
             [ldr_gates[i] for i in [0, 1, 1, 0, 0]], '-r')
    plt.plot([dna_gates[i] for i in [1, 1, 2, 2, 1]],
             [ldr_gates[i] for i in [0, 1, 1, 0, 0]],
             '-r', linewidth=2)

    plt.plot(g1_g2_pos, [0, 0], 'xk', )
    plt.plot(g1_g2_pos, [0, 0], 'ok', markersize=14, markerfacecolor='None')
    plt.xlabel('log10 (DNA)')
    plt.ylabel('LDRtxt intensity')
    dna_lims = get_dnalims(log_dna, x_dna)
    dna_lims = [np.min((dna_lims[0], dna_gates[0]-0.1)),
                np.max((dna_lims[1], dna_gates[3]+0.1))]
    ldr_lims = get_ldrlims(ldrtxt, x_ldr)
    plt.xlim(dna_lims)
    plt.ylim(ldr_lims)


def live_dead(ldrtxt, ldr_gates,
              dna=None, dna_gates=None,
              x_ldr=None, x_dna=None):
    # Notes to self
    # 1. alive = selected+others, where selected is within
    #             inner DNA gate and within LDR
    # 2. dead = anything outside of DNA outer gating and LDR gating
    # 3. total = alive + dead; selected + others + dead
    if x_dna is None:
        x_dna = np.arange(2.5, 8, 0.02)
    if x_ldr is None:
        mx = np.max(ldrtxt.tolist())+0.01
        x_ldr = np.arange(-0.01, mx, 0.0002)
    outcome = [0] * len(ldrtxt)
    ldr_gates = get_ldrgates(ldrtxt, x_ldr)
    ldr_outer = (ldrtxt < ldr_gates[0]) | (ldrtxt > ldr_gates[1])
    outcome = [-1 if b else 0 for b in ldr_outer]
    dead = np.sum([1 for ot in outcome if ot == -1])
    alive = np.sum([1 for ot in outcome if ot >= 0])
    selected = 'DNA information unavailable'
    others = 'DNA information unavailable'

    if dna is not None:
        log_dna = compute_log_dna(dna, x_dna)
        dna_outermost = (log_dna < dna_gates[0]) | (log_dna > dna_gates[3])
        dna_inner = ((log_dna > dna_gates[1]) &
                     (log_dna < dna_gates[2]) &
                     (ldr_outer == False))
        outcome = [-1 if d else 1 if s else 0
                   for d, s in zip((ldr_outer | dna_outermost), dna_inner)]
        alive = np.sum([1 for ot in outcome if ot >= 0])
        dead = np.sum([1 for s in outcome if s == -1])
        selected = np.sum([1 for s in outcome if s == 1])
        others = np.sum([1 for s in outcome if s == 0])
        plt.pie([selected, others, dead],
                labels=['selected', 'others', 'dead'],
                explode=(0.1, 0.1, 0.1), autopct='%1.1f%%')
    else:
        plt.pie([alive, dead], labels=['alive', 'dead'],
                explode=(0.1, 0.1), autopct='%1.1f%%')
    return alive, dead, outcome
