'''Unit tests for the ``dossier.label`` tool.

.. This software is released under an MIT/X11 open source license.
   Copyright 2012-2015 Diffeo, Inc.

'''
from __future__ import absolute_import
from cStringIO import StringIO

import pytest

from kvlayer._local_memory import LocalStorage

from dossier.label import CorefValue, Label, LabelStore
from dossier.label.run import App


@pytest.fixture
def kvlclient():
    c = LocalStorage(app_name='a', namespace='n')
    c._data = {}
    return c


@pytest.fixture
def label_store(kvlclient):
    return LabelStore(kvlclient)


@pytest.fixture
def app(label_store):
    a = App()
    a._label_store = label_store
    a.stdout = StringIO()
    return a


def test_list_short(app, label_store):
    label_store.put(Label('c1', 'c2', 'annotator', CorefValue.Positive,
                          epoch_ticks=1234567890))

    app.runcmd('list', [])

    assert (app.stdout.getvalue() ==
            'c1 ==(1) c2 by annotator at 2009-02-13 23:31:30\n')


def test_list_two(app, label_store):
    label_store.put(Label('c1', 'c2', 'a1', CorefValue.Positive,
                          epoch_ticks=1234567890))
    label_store.put(Label('c1', 'c2', 'a2', CorefValue.Negative,
                          epoch_ticks=1234567890))

    app.runcmd('list', [])

    assert (app.stdout.getvalue() ==
            'c1 ==(1) c2 by a1 at 2009-02-13 23:31:30\n'
            'c1 !=(0) c2 by a2 at 2009-02-13 23:31:30\n')


def test_list_collapses(app, label_store):
    label_store.put(Label('c1', 'c2', 'a1', CorefValue.Positive,
                          epoch_ticks=1234567890))
    label_store.put(Label('c1', 'c2', 'a1', CorefValue.Positive,
                          epoch_ticks=1234567891))
    label_store.put(Label('c1', 'c2', 'a1', CorefValue.Positive,
                          epoch_ticks=1234567892))
    label_store.put(Label('c1', 'c2', 'a2', CorefValue.Negative,
                          epoch_ticks=1234567890))

    app.runcmd('list', [])

    assert (app.stdout.getvalue() ==
            'c1 ==(1) c2 by a1 at 2009-02-13 23:31:32\n'
            'c1 !=(0) c2 by a2 at 2009-02-13 23:31:30\n')


def test_list_deleted(app, label_store):
    label_store.put(Label('c1', 'c2', 'a1', CorefValue.Positive,
                          epoch_ticks=1234567890))
    label_store.put(Label('c1', 'c2', 'a1', CorefValue.Positive,
                          epoch_ticks=1234567891))
    label_store.put(Label('c1', 'c2', 'a1', CorefValue.Positive,
                          epoch_ticks=1234567892))
    label_store.put(Label('c1', 'c2', 'a2', CorefValue.Negative,
                          epoch_ticks=1234567890))

    app.runcmd('list', ['--include-deleted'])

    assert (app.stdout.getvalue() ==
            'c1 ==(1) c2 by a1 at 2009-02-13 23:31:32\n'
            'c1 ==(1) c2 by a1 at 2009-02-13 23:31:31\n'
            'c1 ==(1) c2 by a1 at 2009-02-13 23:31:30\n'
            'c1 !=(0) c2 by a2 at 2009-02-13 23:31:30\n')


def test_list_subtopics(app, label_store):
    label_store.put(Label('c1', 'c2', 'a1', CorefValue.Positive,
                          epoch_ticks=1234567890,
                          subtopic_id1='s1', subtopic_id2='s2'))

    app.runcmd('list', [])

    assert (app.stdout.getvalue() ==
            'c1(s1) ==(1) c2(s2) by a1 at 2009-02-13 23:31:30\n')
