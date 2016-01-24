#!/usr/bin/env python
# vim: set fileencoding=utf-8 tw=96
from __future__ import print_function, unicode_literals

import matplotlib.pyplot as plt
import mwparserfromhell
import operator
import pandas as pd
import re
import requests
import subprocess

import seaborn as sns
sns.set_palette('colorblind', n_colors=4)

from contextlib import contextmanager
from scipy.stats import chisquare


URL = 'https://en.wikipedia.org/w/index.php?title=No_Such_Thing_as_a_Fish&action=raw'
CACHE = 'No_Such_Thing_as_a_Fish.mediawiki.txt'


def fetch():
    try:
        with open(CACHE, 'r') as f:
            return f.read()
    except IOError:
        response = requests.get(URL)
        with open(CACHE, 'w') as f:
            f.write(response.content)
        return response.content


def is_episode_list(t):
    return t.name.strip().lower() == 'episode list'


def get_episodes(markup):
    parsed = mwparserfromhell.parse(markup)
    for t in parsed.filter_templates(matches=is_episode_list):
        ep_number = t.get('EpisodeNumber').value.strip()
        date = t.get('OriginalAirDate').value.strip()
        summary = t.get('ShortSummary').value.strip()

        # N/A is the vinyl special
        if not ep_number.isdigit() and ep_number != 'N/A':
            # skip the One Show special (because the format might have forced an order)
            # and the blooper reel episode.
            print("skipping {!r}".format(ep_number))
            continue

        # The World Cup episodes don't have summaries
        if summary:
            speakers = get_speakers(summary)

            # The audience-fact episodes don't have speakers (which is good: we want to skip
            # those)
            if speakers:
                yield [date] + speakers


def get_speakers(summary):
    return re.findall(r'\(([^()]+)\)\.?\s*$', unicode(summary), re.MULTILINE)


def to_frame(markup):
    rows = get_episodes(markup)
    df = pd.DataFrame(rows, columns=('AirDate',) + positions)
    df.AirDate = pd.to_datetime(df.AirDate)
    df.set_index('AirDate', inplace=True)
    df.sort_index(inplace=True)
    return df


positions = ('First', 'Second', 'Third', 'Fourth')
regular_elves = set('Schreiber Harkin Ptaszynski Murray'.split())


def exclude_guests(df):
    return df[df.apply(lambda row: set(row) == regular_elves, axis=1)]


def get():
    return exclude_guests(to_frame(fetch()))


def summarize(df):
    return df.apply(lambda x: x.value_counts())


def is_nth(df):
    return pd.Panel({
        e: df == e for e in regular_elves
    }).transpose(2, 1, 0)


def cumulative_prob(df, axes=None, title=None):
    c = (df.cumsum().T / range(1, len(df) + 1)).T
    return c.plot(kind='area', title=title)


def main():
    df = get()
    print('{} episodes with regular elves'.format(len(df)))

    s = summarize(df)
    print(s)

    chi_squareds = pd.DataFrame([chisquare(s[c]) for c in s.columns], index=s.columns)
    print(chi_squareds)

    p = is_nth(df)
    for i, position in enumerate(p.items, 1):
        fn = lambda ext: '{}-{}.{}'.format(i, position, ext)
        svg = fn('svg')
        png = fn('png')

        axes = cumulative_prob(p[position],
                               title='Proportion of Facts in {} Position'.format(position))
        axes.figure.savefig(svg)
        subprocess.check_call((
            'inkscape', '--export-dpi=180', '--export-png={}'.format(png), svg,
        ))


if __name__ == '__main__':
    main()
