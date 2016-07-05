'''dossier.label.label

.. This software is released under an MIT/X11 open source license.
   Copyright 2012-2016 Diffeo, Inc.
'''
from __future__ import absolute_import, division, print_function

import cbor
from collections import Container, Hashable
from datetime import datetime
from itertools import combinations, ifilter, imap, product
import logging
from operator import attrgetter, itemgetter
import struct
import time

import enum
from total_ordering import total_ordering


logger = logging.getLogger(__name__)


MAX_SECOND_TICKS = ((60 * 60 * 24) * 365 * 100)
'''The maximum number of seconds supported.

Our kvlayer backend cannot (currently) guarantee a correct ordering
of signed integers, but can guarantee a correct ordering of unsigned
integers.

Labels, however, should be sorted with the most recent label first.
This is trivially possible by negating its epoch ticks.

Because kvlayer cannot guarantee a correct ordering of signed integers,
we avoid the sign switch by subtracting the ticks from an arbitrary
date in the future (UNIX epoch + 100 years).
'''


def time_complement(t):
    return long(MAX_SECOND_TICKS - t)


class CorefValue(enum.Enum):
    '''A human-assigned value for a coreference judgement.

    The judgment is always made with respect to a pair of content
    items.

    :cvar Negative: The two items are not coreferent.
    :cvar Unknown: It is unknown whether the two items are coreferent.
    :cvar Positive: The two items are coreferent.

    '''
    Negative = -1
    Unknown = 0
    Positive = 1

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented

    def __le__(self, other):
        if self.__class__ is other.__class__:
            return self.value <= other.value
        return NotImplemented

    def __gt__(self, other):
        if self.__class__ is other.__class__:
            return self.value > other.value
        return NotImplemented

    def __ge__(self, other):
        if self.__class__ is other.__class__:
            return self.value >= other.value
        return NotImplemented


@total_ordering
class Label(Container, Hashable):
    '''An immutable unit of ground truth data.

    This is a statement that the item at :attr:`content_id1`,
    :attr:`subtopic_id1` refers to (or doesn't) the same thing as the
    item at :attr:`content_id2`, :attr:`subtopic_id2`.  This assertion
    was recorded by :attr:`annotator_id`, a string identifying a user,
    at :attr:`epoch_ticks`, with :class:`CorefValue` :attr:`value`.

    On creation, the tuple is normalized such that the pair of
    `content_id1` and `subtopic_id1` are less than the pair of
    `content_id2` and `subtopic_id2`.

    Labels are comparable, sortable, and hashable.  The sort order
    compares the two content IDs, the two subtopic IDs,
    :attr:`annotator_id`, :attr:`epoch_ticks` (most recent is
    smallest), and then other fields.

    .. attribute:: content_id1

       The first content ID.

    .. attribute:: content_id2

       The second content ID.

    .. attribute:: annotator_id

       An identifier of the user making this assertion.

    .. attribute:: value

       A :class:`CorefValue` stating whether this is a positive or
       negative coreference assertion.

    .. attribute:: subtopic_id1

       An identifier defining a section or region of
       :attr:`content_id1`.

    .. attribute:: subtopic_id2

       An identifier defining a section or region of
       :attr:`content_id2`.

    .. attribute:: epoch_ticks

       The time at which :attr:`annotator_id` made this assertion,
       in seconds since the Unix epoch.

    .. attribute:: rating

       An additional score showing the relative importance of this
       label, mirroring :class:`streamcorpus.Rating`.

    .. attribute:: meta

       Any additional meta data about this label, structured as
       a dictionary.

    .. automethod:: __init__
    .. automethod:: __contains__
    .. automethod:: other
    .. automethod:: subtopic_for
    .. automethod:: same_subject_as
    .. automethod:: most_recent

    '''

    def __init__(self, content_id1, content_id2, annotator_id, value,
                 subtopic_id1=None, subtopic_id2=None, epoch_ticks=None,
                 rating=None, meta=None):
        '''Create a new label.

        Parameters are assigned to their corresponding fields, with
        some normalization.  If `value` is an :class:`int`, the
        corresponding :class:`CorefValue` is used instead.  If
        `epoch_ticks` is :const:`None` then the current time is
        used.  If `rating` is :const:`None` then it will be 1 if
        `value` is :attr:`CorefValue.Positive` and 0 otherwise.

        '''
        super(Label, self).__init__()

        # Fix up and provide defaults for various parameters
        if isinstance(value, int):
            value = CorefValue(value)
        if epoch_ticks is None:
            epoch_ticks = long(time.time())
        if subtopic_id1 is None:
            subtopic_id1 = ''
        if subtopic_id2 is None:
            subtopic_id2 = ''

        if value == CorefValue.Positive:
            if rating is None:
                rating = 1
        else:
            rating = 0

        # Fix ordering of content, subtopic pairs
        if ((content_id2 < content_id1 or
             (content_id2 == content_id1 and subtopic_id2 < subtopic_id1))):
            self.content_id1 = content_id2
            self.subtopic_id1 = subtopic_id2
            self.content_id2 = content_id1
            self.subtopic_id2 = subtopic_id1
        else:
            self.content_id1 = content_id1
            self.subtopic_id1 = subtopic_id1
            self.content_id2 = content_id2
            self.subtopic_id2 = subtopic_id2

        self.annotator_id = annotator_id
        self.value = value
        self.epoch_ticks = epoch_ticks
        self.rating = rating

        self.meta = meta
        if self.meta is None:
            self.meta = {}

    def update(self, **kwargs):
        '''Creates a new label with the modifications given.

        ``kwargs`` supports the same parameters as this class'
        constructor. A new label is created from a copy of
        ``self`` with the parameters given as overrides.

        For example, ``lab.update()`` creates a copy of ``lab``.
        Another example, ``lab.update(annotator_id='foo')``
        creates a copy of ``lab`` except the ``annotator_id`` field
        is set to ``'foo'``.

        (This is like ``namedtuple._replace`` or record updates in
        functional languages.)
        '''
        return Label(**dict(self.as_dict(), **kwargs))

    def as_dict(self):
        '''Returns this label as a Python dictionary.'''
        return {
            'content_id1': self.content_id1, 'subtopic_id1': self.subtopic_id1,
            'content_id2': self.content_id2, 'subtopic_id2': self.subtopic_id2,
            'annotator_id': self.annotator_id, 'value': self.value,
            'epoch_ticks': self.epoch_ticks, 'rating': self.rating,
            'meta': self.meta,
        }

    def __contains__(self, v):
        '''Tests membership of identifiers.

        If `v` is a tuple of ``(content_id, subtopic_id)``, then the
        pair is checked for membership. Otherwise, `v` must be a
        :class:`str` and is checked for equality to one of the content
        ids in this label.

        As a special case, if `v` is ``(content_id, None)``, then
        `v` is treated as if it were ``content_id``.

        >>> l = Label('c1', 'c2', 'a', 1)
        >>> 'c1' in l
        True
        >>> 'a' in l
        False
        >>> ('c1', None) in l
        True
        >>> ('c1', 's1') in l
        False
        >>> ll = Label('c1', 'c2', 'a', 1, 's1', 's2')
        >>> 'c1' in l
        True
        >>> ('c1', None) in l
        True
        >>> ('c1', 's1') in l
        True

        '''
        if isinstance(v, tuple) and len(v) == 2 and v[1] is None:
            v = v[0]

        if isinstance(v, tuple) and len(v) == 2:
            cid, subid = v
            cid1, subid1 = self.content_id1, self.subtopic_id1
            cid2, subid2 = self.content_id2, self.subtopic_id2
            return (cid == cid1 and subid == subid1) \
                or (cid == cid2 and subid == subid2)
        else:
            return v == self.content_id1 or v == self.content_id2

    def other(self, content_id):
        '''Returns the other content id.

        If ``content_id == self.content_id1``, then return
        ``self.content_id2`` (and vice versa).  Raises
        :exc:`exceptions.KeyError` if `content_id` is neither one.

        >>> l = Label('c1, 'c2', 'a', 1)
        >>> l.other('c1')
        'c2'
        >>> l.other('c2')
        'c1'
        >>> l.other('a')
        Traceback (most recent call last):
            ...
        KeyError: 'a'

        '''
        if content_id == self.content_id1:
            return self.content_id2
        elif content_id == self.content_id2:
            return self.content_id1
        else:
            raise KeyError(content_id)

    def subtopic_for(self, content_id):
        '''Get the subtopic id that corresponds with a content id.

        >>> l = Label('c1', 'c2', 'a', 1, 's1', 's2')
        >>> l.subtopic_for('c1')
        's1'
        >>> l.subtopic_for('c2')
        's2'
        >>> l.subtopic_for('a')
        Traceback (most recent call last):
            ...
        KeyError: 'a'

        :param str content_id: content ID to look up
        :return: subtopic ID for `content_id`
        :raise exceptions.KeyError: if `content_id` is neither
          content ID in this label

        '''

        if content_id == self.content_id1:
            return self.subtopic_id1
        elif content_id == self.content_id2:
            return self.subtopic_id2
        else:
            raise KeyError(content_id)

    def __lt__(self, other):
        if self.content_id1 != other.content_id1:
            return self.content_id1 < other.content_id1
        if self.content_id2 != other.content_id2:
            return self.content_id2 < other.content_id2
        if self.subtopic_id1 != other.subtopic_id1:
            return self.subtopic_id1 < other.subtopic_id1
        if self.subtopic_id2 != other.subtopic_id2:
            return self.subtopic_id2 < other.subtopic_id2
        if self.annotator_id != other.annotator_id:
            return self.annotator_id < other.annotator_id
        if self.epoch_ticks != other.epoch_ticks:
            # opposite ordering here (consciously -- newer is smaller)
            return self.epoch_ticks > other.epoch_ticks
        if self.value is not other.value:
            return self.value < other.value
        if self.rating != other.rating:
            return self.rating < other.rating
        return False  # self == other

    def __eq__(self, other):
        if self.content_id1 != other.content_id1:
            return False
        if self.content_id2 != other.content_id2:
            return False
        if self.subtopic_id1 != other.subtopic_id1:
            return False
        if self.subtopic_id2 != other.subtopic_id2:
            return False
        if self.annotator_id != other.annotator_id:
            return False
        if self.epoch_ticks != other.epoch_ticks:
            return False
        if self.value is not other.value:
            return False
        if self.rating != other.rating:
            return False
        return True

    def same_subject_as(self, other):
        '''Determine if two labels are about the same thing.

        This predicate returns :const:`True` if `self` and `other`
        have the same content IDs, subtopic IDs, and annotator ID.
        The other fields may have any value.

        >>> t = time.time()
        >>> l1 = Label('c1', 'c2', 'a', CorefValue.Positive,
        ...            epoch_ticks=t)
        >>> l2 = Label('c1', 'c2', 'a', CorefValue.Negative,
        ...            epoch_ticks=t)
        >>> l1.same_subject_as(l2)
        True
        >>> l1 == l2
        False

        '''
        if self.content_id1 != other.content_id1:
            return False
        if self.content_id2 != other.content_id2:
            return False
        if self.subtopic_id1 != other.subtopic_id1:
            return False
        if self.subtopic_id2 != other.subtopic_id2:
            return False
        if self.annotator_id != other.annotator_id:
            return False
        return True

    def changed(self, other):
        '''Returns true if ``other`` is modified from ``self`.

        More specifically, returns true if and only if ``self``
        and ``other`` share the same subject but have different
        coref/rating values.
        '''
        return (self.same_subject_as(other) and
                (self.value != other.value or self.rating != other.rating))

    @staticmethod
    def most_recent(labels):
        '''Filter an iterator to return the most recent for each subject.

        `labels` is any iterator over :class:`Label` objects.  It
        should be sorted with the most recent first, which is the
        natural sort order that :func:`sorted` and the
        :class:`LabelStore` adapter will return.  The result of this
        is a generator of the same labels but with any that are not
        the most recent for the same subject (according to
        :meth:`same_subject_as`) filtered out.

        '''
        prev_label = None
        for label in labels:
            if prev_label is None or not label.same_subject_as(prev_label):
                yield label
            prev_label = label

    @staticmethod
    def diff(old, new):
        '''Returns a *diff* of two sets of labels.

        The diff returned represents the changes required to the set
        of ``old`` labels in order to provide the same semantic meaning
        as the set of ``new`` labels. Thus, the diff is a Python dictionary
        with three keys: ``add``, ``delete`` and ``change``. All three
        keys map to a sequence of labels.

        ``add`` corresponds to the labels that are in ``new`` but not in
        ``old``.

        ``delete`` corresponds to the labels that are in ``old`` but not
        in ``new``.

        ``change`` corresponds to the labels that are in both ``old``
        and ``new`` but have different coref/rating values.
        '''
        # A wrapper type for a more relaxed label equality comparison.
        # (We use a wrapper type so that its easy to unwrap it.)
        class SubjectLabel(object):
            def __init__(self, lab):
                self.lab = lab

            def changed(self, other):
                return self.lab.changed(other.lab)

            def __eq__(self, other):
                return self.lab.same_subject_as(other.lab)

            def __hash__(self):
                return hash((self.lab.content_id1, self.lab.content_id2,
                             self.lab.subtopic_id1, self.lab.subtopic_id2,
                             self.lab.annotator_id))

        old, new = set(map(SubjectLabel, old)), set(map(SubjectLabel, new))
        add, delete = list(new.difference(old)), list(old.difference(new))
        change = map(itemgetter(1),
                     ifilter(lambda (o, n): o.changed(n), product(old, new)))
        unwrap = attrgetter('lab')
        return {
            'add': map(unwrap, add),
            'delete': map(unwrap, delete),
            'change': map(unwrap, change),
        }

    def __hash__(self):
        return (hash(self.content_id1) ^
                hash(self.content_id2) ^
                hash(self.subtopic_id1) ^
                hash(self.subtopic_id2) ^
                hash(self.annotator_id) ^
                hash(self.epoch_ticks) ^
                hash(self.value) ^
                hash(self.rating))

    def __str__(self):
        res = repr(self.content_id1)[1:-1]  # strip quotes
        if self.subtopic_id1:
            res += '(' + repr(self.subtopic_id1)[1:-1] + ')'
        if self.value is CorefValue.Positive:
            res += ' =='
        elif self.value is CorefValue.Unknown:
            res += ' ??'
        elif self.value is CorefValue.Negative:
            res += ' !='
        else:
            res += ' **'
        res += '(' + str(self.rating) + ') '
        res += repr(self.content_id2)[1:-1]  # strip quotes
        if self.subtopic_id2:
            res += '(' + repr(self.subtopic_id2)[1:-1] + ')'
        res += ' by ' + self.annotator_id
        res += ' at ' + str(datetime.utcfromtimestamp(self.epoch_ticks))
        return res

    def __repr__(self):
        return ('Label('
                'content_id1={0.content_id1}, '
                'content_id2={0.content_id2}, '
                'annotator_id={0.annotator_id}, '
                'value={0.value}, '
                'subtopic_id1={0.subtopic_id1}, '
                'subtopic_id2={0.subtopic_id2}, '
                'epoch_ticks={0.epoch_ticks}, '
                'rating={0.rating})'.format(self))


class LabelStore(object):
    '''A label database.

    .. automethod:: __init__
    .. automethod:: put
    .. automethod:: get
    .. automethod:: directly_connected
    .. automethod:: connected_component
    .. automethod:: expand
    .. automethod:: everything
    .. automethod:: delete_all
    '''
    config_name = 'dossier.label'
    TABLE = 'label'

    _kvlayer_namespace = {
        # (cid1, cid2, subid1, subid2, annotator_id, time) -> value
        # N.B. The `long` type here is for the benefit of the underlying
        # database storage. It will hopefully result in a storage type
        # that is big enough to contain milliseconds epoch ticks. (A 64 bit
        # integer is more than sufficient, which makes `long` unnecessary from
        # a Python 2 perspective.)
        TABLE: (str, str, str, str, str, long),
    }

    def __init__(self, kvlclient):
        '''Create a new label store.

        :param kvlclient: kvlayer client
        :type kvlclient: :class:`kvlayer._abstract_storage.AbstractStorage`
        :rtype: :class:`LabelStore`
        '''
        self.kvl = kvlclient
        self.kvl.setup_namespace(self._kvlayer_namespace)

    def put(self, *labels):
        '''Add a new label to the store.

        :param label: label
        :type label: :class:`Label`
        '''
        puts = []
        for label in labels:
            k1, k2 = self._keys_from_label(label)
            v = self._value_from_label(label)
            puts.append((k1, v))
            puts.append((k2, v))
        self.kvl.put(self.TABLE, *puts)

    def _keys_from_label(self, label):
        # `label` is stored under both normal and swapped key tuples,
        # so that we can efficiently find c2<->c1 labels
        k1 = (label.content_id1, label.content_id2,
              label.subtopic_id1, label.subtopic_id2,
              label.annotator_id, time_complement(label.epoch_ticks))
        k2 = (label.content_id2, label.content_id1,
              label.subtopic_id2, label.subtopic_id1,
              label.annotator_id, time_complement(label.epoch_ticks))
        return k1, k2

    def _value_from_label(self, label):
        # Pack value and rating into a single byte, since both will likely
        # be small integers.
        to_pack = (label.value.value+1) | (label.rating << 4)
        v = struct.pack('B', to_pack)

        # Encode the metadata.
        meta_ser = cbor.dumps(label.meta)

        return v + meta_ser

    def get(self, cid1, cid2, annotator_id, subid1='', subid2=''):
        '''Retrieve a label from the store.

        When ``subid1`` and ``subid2`` are empty, then a label without
        subtopic identifiers will be returned.

        If there are multiple labels stored with the same parts,
        the single most recent one will be returned.  If there are
        no labels with these parts, :exc:`exceptions.KeyError` will
        be raised.

        :param str cid1: content id
        :param str cid2: content id
        :param str annotator_id: annotator id
        :param str subid1: subtopic id
        :param str subid2: subtopic id
        :rtype: :class:`Label`
        :raises: :exc:`KeyError` if no label could be found.

        '''
        t = (cid1, cid2, subid1, subid2, annotator_id)

        # We return the first result because the `kvlayer` abstraction
        # guarantees that the first result will be the most recent entry
        # for this particular key (since the timestamp is inserted as a
        # complement value).
        for k, v in self.kvl.scan(self.TABLE, (t, t)):
            return self._label_from_kvlayer(k, v)
        raise KeyError(t)

    def _label_from_kvlayer(self, k, v):
        '''Make a label from a kvlayer row.'''
        (content_id1, content_id2, subtopic_id1, subtopic_id2,
         annotator_id, inverted_epoch_ticks) = k
        epoch_ticks = time_complement(inverted_epoch_ticks)

        (unpacked,) = struct.unpack('B', v[0])
        value = (unpacked & 15) - 1
        rating = (unpacked >> 4)
        meta = None
        if len(v) > 1:
            meta = cbor.loads(v[1:])

        return Label(content_id1=content_id1,
                     content_id2=content_id2,
                     annotator_id=annotator_id,
                     value=value,
                     subtopic_id1=subtopic_id1,
                     subtopic_id2=subtopic_id2,
                     epoch_ticks=epoch_ticks,
                     rating=rating,
                     meta=meta)

    def directly_connected(self, ident):
        '''Return a generator of labels connected to ``ident``.

        ``ident`` may be a ``content_id`` or a ``(content_id,
        subtopic_id)``.

        If no labels are defined for ``ident``, then the generator
        will yield no labels.

        Note that this only returns *directly* connected labels. It
        will not follow transitive relationships.

        :param ident: content id or (content id and subtopic id)
        :type ident: ``str`` or ``(str, str)``
        :rtype: generator of :class:`Label`
        '''
        content_id, subtopic_id = normalize_ident(ident)
        return self.everything(include_deleted=False,
                               content_id=content_id,
                               subtopic_id=subtopic_id)

    def split_by_connected_component(self, idents):
        '''Split idents into equivalence classes based on connected
        components.
        '''
        idents_remaining = set(idents)
        connected_components = []
        for ident in idents:
            if ident not in idents_remaining:
                continue

            idents_remaining.remove(ident)

            connected_component = [ident]
            for label in self.connected_component(ident):
                cids = label.content_id1, label.content_id2
                for cid in cids:
                    if cid in idents_remaining:
                        connected_component.append(cid)
                        idents_remaining.remove(cid)

            connected_components.append(sorted(connected_component))
        return connected_components

    def connected_component(self, ident):
        '''Return a connected component generator for ``ident``.

        ``ident`` may be a ``content_id`` or a ``(content_id,
        subtopic_id)``.

        Given an ``ident``, return the corresponding connected
        component by following all positive transitivity relationships.

        For example, if ``(a, b, 1)`` is a label and ``(b, c, 1)`` is
        a label, then ``connected_component('a')`` will return both
        labels even though ``a`` and ``c`` are not directly connected.

        (Note that even though this returns a generator, it will still
        consume memory proportional to the number of labels in the
        connected component.)

        :param ident: content id or (content id and subtopic id)
        :type ident: ``str`` or ``(str, str)``
        :rtype: generator of :class:`Label`
        '''
        ident = normalize_ident(ident)
        done = set()  # set of cids that we've queried with
        todo = set([ident])  # set of cids to do a query for
        labels = set()
        while todo:
            ident = todo.pop()
            done.add(ident)
            for label in self.directly_connected(ident):
                if label.value != CorefValue.Positive:
                    continue
                ident1, ident2 = idents_from_label(
                    label, subtopic=ident_has_subtopic(ident))
                if ident1 not in done:
                    todo.add(ident1)
                if ident2 not in done:
                    todo.add(ident2)

                if label not in labels:
                    labels.add(label)
                    yield label

    def expand(self, ident):
        '''Return expanded set of labels from a connected component.

        The connected component is derived from ``ident``. ``ident``
        may be a ``content_id`` or a ``(content_id, subtopic_id)``.
        If ``ident`` identifies a subtopic, then expansion is done
        on a subtopic connected component (and expanded labels retain
        subtopic information).

        The labels returned by :meth:`LabelStore.connected_component`
        contains only the :class:`Label` stored in the
        :class:`LabelStore`, and does not include the labels you can
        infer from the connected component. This method returns both
        the data-backed labels and the inferred labels.

        Subtopic assignments of the expanded labels will be empty. The
        ``annotator_id`` will be an arbitrary ``annotator_id`` within
        the connected component.

        :param str content_id: content id
        :param value: coreferent value
        :type value: :class:`CorefValue`
        :rtype: ``list`` of :class:`Label`
        '''
        subtopic = ident_has_subtopic(normalize_ident(ident))
        labels = list(self.connected_component(ident))
        labels.extend(expand_labels(labels, subtopic=subtopic))
        return labels

    def negative_inference(self, content_id):
        '''Return a generator of inferred negative label relationships
        centered on ``content_id``.

        Negative labels are inferred by getting all other content ids
        connected to ``content_id`` through a negative label, then
        running :meth:`LabelStore.negative_label_inference` on those
        labels. See :meth:`LabelStore.negative_label_inference` for
        more information.
        '''
        neg_labels = ifilter(lambda l: l.value == CorefValue.Negative,
                             self.directly_connected(content_id))
        for label in neg_labels:
            label_inf = self.negative_label_inference(label)
            for label in label_inf:
                yield label

    def negative_label_inference(self, label):
        '''Return a generator of inferred negative label relationships.

        Construct ad-hoc negative labels between ``label.content_id1``
        and the positive connected component of ``label.content_id2``,
        and ``label.content_id2`` to the connected component of
        ``label.content_id1``.

        Note this will allocate memory proportional to the size of the
        connected components of ``label.content_id1`` and
        ``label.content_id2``.
        '''
        assert label.value == CorefValue.Negative

        yield label

        cid2_comp = self.connected_component(label.content_id2)
        for comp_label in cid2_comp:
            comp_cids = (comp_label.content_id1,
                         comp_label.content_id2)
            for comp_cid in comp_cids:
                if not comp_cid == label.content_id2:
                    yield Label(label.content_id1, comp_cid,
                                'auto', CorefValue.Negative)

        cid1_comp = self.connected_component(label.content_id1)
        for comp_label in cid1_comp:
            comp_cids = (comp_label.content_id1,
                         comp_label.content_id2)
            for comp_cid in comp_cids:
                if not comp_cid == label.content_id1:
                    yield Label(label.content_id2, comp_cid,
                                'auto', CorefValue.Negative)

    def _filter_keys(self, content_id=None, subtopic_id=None):
        '''Filter out-of-order labels by key tuple.

        :class:`Label` always sorts by `(cid1,cid2,sid1,sid2)`, but
        for efficient lookups on `cid2` this class also stores in
        order `(cid2,cid1,sid2,sid1)`.  Filter out things that are
        in the wrong order.  But, if an original query specified
        `content_id` or `subtopic_id`, account for the possibility
        that something might be apparently out-of-order but its
        dual will not be in the query at all.

        '''
        def accept(kvp):
            (content_id1, content_id2, subtopic_id1, subtopic_id2,
             annotator_id, inverted_epoch_ticks) = kvp[0]
            if content_id is None:
                # We're scanning everything, so accept the label if
                # it's the natural order; l.content_id1 == cid1
                return (content_id1 < content_id2 or
                        (content_id1 == content_id2 and
                         subtopic_id1 <= subtopic_id2))
            assert content_id1 == content_id  # because that's the scan range
            # If we're not looking for subtopic IDs, then accept records
            # matching the content ID that are in natural order
            if subtopic_id is None:
                if content_id2 != content_id:
                    return True  # will never see its dual
                return subtopic_id1 <= subtopic_id2
            # The scan range doesn't include subtopic IDs (the key schema
            # is oriented towards querying content-to-content labels)
            # so we need to accept records where either part matches
            # (if both parts match then the record is its own dual)
            if subtopic_id == subtopic_id1:
                return True
            if content_id == content_id2 and subtopic_id == subtopic_id2:
                return True
            return False
        return accept

    def everything(self, include_deleted=False, content_id=None,
                   subtopic_id=None, prefix=None):
        '''Returns a generator of all labels in the store.

        If `include_deleted` is :const:`True`, labels that have been
        overwritten with more recent labels are also included.  If
        `content_id` is not :const:`None`, only labels for that
        content ID are retrieved; and then if `subtopic_id` is not
        :const:`None`, only that subtopic is retrieved, else all
        subtopics are retrieved.  If `content_id` is :const:`None` but
        `prefix` is not, then only labels with at least one content ID
        beginning with `prefix` will be returned.  The returned labels
        will always be q in sorted order, content IDs first, and with
        those with the same content, subtopic, and annotator IDs
        sorted newest first.

        :rtype: generator of :class:`Label`

        '''
        if content_id is not None:
            ranges = [((content_id,), (content_id,))]
        elif prefix is not None:
            # This is the cheap, easy, and wrong way to do this
            ranges = [((prefix,), (prefix + b'\xff',))]
        else:
            ranges = []
        labels = self.kvl.scan(self.TABLE, *ranges)
        labels = ifilter(self._filter_keys(content_id, subtopic_id), labels)
        labels = imap(lambda p: self._label_from_kvlayer(*p), labels)
        if not include_deleted:
            labels = Label.most_recent(labels)
        return labels

    def delete_all(self):
        '''Deletes all labels in the store.'''
        self.kvl.clear_table(self.TABLE)

    def delete(self, *labels):
        '''Delete `labels` from the store, which involves deleting two
        records for each :class:`Label`.

        :rtype: None
        :raises: :exc:`KeyError` if any of the `labels` could not be found.

        '''
        deletes = []
        for label in labels:
            k1, k2 = self._keys_from_label(label)
            deletes.append(k1)
            deletes.append(k2)
        self.kvl.delete(self.TABLE, *deletes)

    def apply_diff(self, diff):
        '''Applies a diff to the label table.

        A ``diff`` is a dictionary with three keys: ``add``, ``delete``
        and ``change``. Each key should map to a list of labels.

        ``add`` corresponds to the labels that are in ``new`` but not in
        ``old``.

        ``delete`` corresponds to the labels that are in ``old`` but not
        in ``new``.

        ``change`` corresponds to the labels that are in both ``old``
        and ``new`` but have different coref/rating values.
        '''
        # add and change are easy---just put the labels.
        # delete is a little trickier. We need to scrub out the impact of
        # the previous label without actually deleting it. For this, we
        # use an unknown coref value.
        insert = (
            diff['add'] +
            diff['change'] +
            [lab.update(value=CorefValue.Unknown)
             for lab in diff['delete']]
        )
        self.put(*insert)


def unordered_pair_eq(pair1, pair2):
    '''Performs pairwise unordered equality.

    ``pair1`` == ``pair2`` if and only if
    ``frozenset(pair1)`` == ``frozenset(pair2)``.
    '''
    (x1, y1), (x2, y2) = pair1, pair2
    return (x1 == x2 and y1 == y2) or (x1 == y2 and y1 == x2)


def normalize_pair(x, y):
    '''Normalize a pair of values.

    Returns ``(y, x)`` if and only if ``y < x`` and ``(x, y)``
    otherwise.
    '''
    if y < x:
        return y, x
    else:
        return x, y


def expand_labels(labels, subtopic=False):
    '''Expand a set of labels that define a connected component.

    ``labels`` must define a *positive* connected component: it is all
    of the edges that make up the *single* connected component in the
    :class:`LabelStore`. expand will ignore subtopic assignments, and
    annotator_id will be an arbitrary one selected from ``labels``.

    Note that this function only returns the expanded labels, which
    is guaranteed to be disjoint with the given ``labels``. This
    requirement implies that ``labels`` is held in memory to ensure
    that no duplicates are returned.

    If ``subtopic`` is ``True``, then it is assumed that ``labels``
    defines a ``subtopic`` connected component. In this case, subtopics
    are included in the expanded labels.

    :param labels: iterable of :class:`Label` for the connected component.
    :rtype: generator of expanded :class:`Label`s only
    '''
    labels = list(labels)
    assert all(lab.value == CorefValue.Positive for lab in labels)

    # Anything to expand?
    if len(labels) == 0:
        return

    annotator = labels[0].annotator_id

    data_backed = set()
    connected_component = set()
    for label in labels:
        ident1, ident2 = idents_from_label(label, subtopic=subtopic)
        data_backed.add(normalize_pair(ident1, ident2))
        connected_component.add(ident1)
        connected_component.add(ident2)

    # We do not want to rebuild the Labels we already have,
    # because they have true annotator_id and subtopic
    # fields that we may want to preserve.
    for ident1, ident2 in combinations(connected_component, 2):
        if normalize_pair(ident1, ident2) not in data_backed:
            (cid1, subid1), (cid2, subid2) = ident1, ident2
            yield Label(cid1, cid2, annotator, CorefValue.Positive,
                        subtopic_id1=subid1, subtopic_id2=subid2)


def normalize_ident(ident):
    '''Splits a generic identifier.

    If ``ident`` is a tuple, then ``(ident[0], ident[1])`` is returned.
    Otherwise, ``(ident[0], None)`` is returned.
    '''
    if isinstance(ident, tuple) and len(ident) == 2:
        return ident[0], ident[1]  # content_id, subtopic_id
    else:
        return ident, None


def ident_has_subtopic(ident):
    return ident[1] is not None


def idents_from_label(lab, subtopic=False):
    '''Returns the "ident" of a label.

    If ``subtopic`` is ``True``, then a pair of pairs is returned,
    where each pair corresponds to the content id and subtopic id in
    the given label.

    Otherwise, a pair of pairs is returned, but the second element of each
    pair is always ``None``.

    This is a helper function that is useful for dealing with generic
    label identifiers.
    '''
    if not subtopic:
        return (lab.content_id1, None), (lab.content_id2, None)
    else:
        return (
            (lab.content_id1, lab.subtopic_id1),
            (lab.content_id2, lab.subtopic_id2),
        )
