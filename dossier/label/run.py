'''
.. This software is released under an MIT/X11 open source license.
   Copyright 2012-2014 Diffeo, Inc.

``dossier.label`` command line tool
===================================

``dossier.label`` is a command line application for viewing the raw label
data inside the database. Generally, this is a debugging tool for developers.

Run ``dossier.label --help`` for the available commands.
'''
from __future__ import absolute_import, division, print_function
import argparse
from itertools import groupby, imap, islice

import cbor
import kvlayer
import yakonfig

from dossier.label import CorefValue, Label, LabelStore


def label_to_dict(lab):
    return {
        'content_id1': lab.content_id1,
        'content_id2': lab.content_id2,
        'annotator_id': lab.annotator_id,
        'value': lab.value.value,
        'subtopic_id1': lab.subtopic_id1,
        'subtopic_id2': lab.subtopic_id2,
        'epoch_ticks': lab.epoch_ticks,
        'rating': lab.rating,
    }


def dict_to_label(d):
    return Label(
        content_id1=d['content_id1'],
        content_id2=d['content_id2'],
        annotator_id=d['annotator_id'],
        value=CorefValue(d['value']),
        subtopic_id1=d.get('subtopic_id1', None),
        subtopic_id2=d.get('subtopic_id2', None),
        epoch_ticks=d.get('epoch_ticks', None),  # will become time.time()
        rating=d.get('rating', None),
    )


class App(yakonfig.cmd.ArgParseCmd):
    def __init__(self, *args, **kwargs):
        yakonfig.cmd.ArgParseCmd.__init__(self, *args, **kwargs)
        self._label_store = None

    @property
    def label_store(self):
        if self._label_store is None:
            self._label_store = LabelStore(kvlayer.client())
        return self._label_store

    def args_list(self, p):
        p.add_argument('--include-deleted', action='store_true',
                       help='When set, show deleted labels.')

    def do_list(self, args):
        labels = self.label_store.everything(
            include_deleted=args.include_deleted)
        for k, group in groupby(sorted(labels)):
            self.stdout.write('%s\n' % (k,))
            for lab in islice(group, 1, None):
                self.stdout.write('    %s\n' % repr(lab))

    def args_dump_all(self, p):
        p.add_argument('--exclude-deleted', action='store_true',
                       help='When set, only the most recent labels are '
                            'dumped.')

    def do_dump_all(self, args):
        labels = list(imap(label_to_dict, self.label_store.everything(
            include_deleted=not args.exclude_deleted)))
        cbor.dump(labels, fp=self.stdout)

    def args_show_all(self, p):
        p.add_argument('--exclude-deleted', action='store_true',
                       help='When set, only the most recent labels are '
                            'dumped.')

    def do_show_all(self, args):
        labels = list(imap(label_to_dict, self.label_store.everything(
            include_deleted=not args.exclude_deleted)))
        for label in labels:
            print('%r' % label)

    def args_load(self, p):
        p.add_argument('fpath', nargs='?', default=None,
                       help='File path containing label data. When absent, '
                            'stdin is used.')

    def do_load(self, args):
        if args.fpath is None:
            self._load(self.stdin)
        else:
            with open(args.fpath, 'r') as fp:
                self._load(fp)

    def _load(self, fp):
        for record in cbor.load(fp):
            label = dict_to_label(record)
            self.label_store.put(label)

    def args_get(self, p):
        p.add_argument('content_id', type=str,
                       help='Show all labels directly ascribed to content_id')
        p.add_argument('--value', type=int, choices=[-1, 0, 1],
                       default=None,
                       help='Only show labels with this coreferent value.')

    def do_get(self, args):
        '''Get labels directly connected to a content item.'''
        for label in self.label_store.directly_connected(args.content_id):
            if args.value is None or label.value.value == args.value:
                self.stdout.write('{}\n'.format(label))

    def args_connected(self, p):
        p.add_argument('content_id', type=str,
                       help='Show all labels connected to content_id')

    def do_connected(self, args):
        '''Find a connected component from positive labels on an item.'''
        connected = self.label_store.connected_component(args.content_id)
        for label in connected:
            self.stdout.write('{}\n'.format(label))

    def args_delete_all(self, p):
        pass

    def do_delete_all(self, args):
        answer = raw_input('Are you absolutely sure? [y/n] ').strip().lower()
        if answer and answer[0] == 'y':
            self.label_store.delete_all()


def main():
    p = argparse.ArgumentParser(
        description='Interact with DossierStack truth data.')
    app = App()
    app.add_arguments(p)
    args = yakonfig.parse_args(p, [kvlayer, yakonfig])
    app.main(args)
