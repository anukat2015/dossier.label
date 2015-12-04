'''dossier.label.relation_label

.. This software is released under an MIT/X11 open source license.
   Copyright 2012-2015 Diffeo, Inc.
'''
from __future__ import absolute_import

import cbor
from collections import Container, Hashable
import logging
import time

import enum
from itertools import imap, ifilter
from total_ordering import total_ordering

from dossier.label.label import time_complement, LabelStore

logger = logging.getLogger(__name__)


class RelationStrength(enum.Enum):
    '''A human-assigned value for the relation type.

    NONE - these entities are not related in any meaningful way.
    UNKNOWN - the relationship between these entities are unknown.
    AKA - The two entities are the same (coreference).
    WEAK - The entities are related but not in a particularly interesting way.
    STRONG - The entities are strongly related.
    '''
    NONE = -1
    UNKNOWN = 0
    WEAK = 1
    STRONG = 2
    AKA = 3

    @property
    def is_positive(self):
        return (self == RelationStrength.WEAK or
                self == RelationStrength.STRONG or
                self == RelationStrength.AKA)

    @property
    def is_negative(self):
        return not self.is_positive

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

    def __ge__(self, other):
        if self.__class__ is other.__class__:
            return self.value >= other.value
        return NotImplemented

@total_ordering
class RelationLabel(Container, Hashable):
    '''An immutable unit of ground truth data for relationships.

    A ``RelationLabel`` is a statement saying that the item at
    :attr:`content_id1` is related to the item at
    :attr:`content_id2`. The statement was recorded by
    :attr:`annotator_id`, a string identifying a user, at
    :attr:`epoch_ticks`. The strength of the relationship is specified
    by :attr:`rel_strength`, which is of type :class:`RelationStrength`.

    On creation, the tuple is normalized such that `content_id1` is
    less than `content_id2`.

    RelationLabels are comparable, sortable, and hashable. The sort
    order compares the two content ids, the annotator id, the epoch
    ticks, and then rel_strength.

    .. attribute:: content_id1

       The first content ID

    .. attribute:: content_id2

       The second content ID

    .. attribute:: annotator_id

       An identifier of the user making this label.

    .. attribute:: rel_strength

       A :class:`RelationStrength` describing the strength of the relationship.

    .. attribute:: epoch_ticks

       The time at which :attr:`annotator_id` made this assertion, in
       seconds since the Unix epoch.

    .. attribute:: meta

       Any additional meta data about this relation label, as a
       dictionary.
    '''

    def __init__(self, content_id1, content_id2, annotator_id, rel_strength,
                 epoch_ticks=None, meta=None):
        super(RelationLabel, self).__init__()

        if isinstance(rel_strength, int):
            rel_strength = RelationStrength(rel_strength)
        if epoch_ticks is None:
            epoch_ticks = long(time.time())

        if content_id2 < content_id1:
            self.content_id1 = content_id2
            self.content_id2 = content_id1
        else:
            self.content_id1 = content_id1
            self.content_id2 = content_id2

        self.annotator_id = annotator_id
        self.rel_strength = rel_strength
        self.epoch_ticks = epoch_ticks
        self.meta = meta
        if self.meta is None:
            self.meta = {}

    def as_dict(self):
        '''Returns this RelationLabel as a Python dictionary.
        '''
        return {
            'content_id1': self.content_id1,
            'content_id2': self.content_id2,
            'rel_strength': self.rel_strength,
            'annotator_id': self.annotator_id,
            'epoch_ticks': self.epoch_ticks,
            'meta': self.meta,
        }

    def __contains__(self, cid):
        '''Checks if a cid is one of the identifiers in this RelationLabel.
        '''
        return cid == self.content_id1 or cid == self.content_id2

    def other(self, cid):
        if cid == self.content_id1:
            return self.content_id2
        elif cid == self.content_id2:
            return self.content_id1
        else:
            raise KeyError(cid)

    def __lt__(self, other):
        if self.content_id1 != other.content_id1:
            return self.content_id1 < other.content_id1
        if self.content_id2 != other.content_id2:
            return self.content_id2 < other.content_id2
        if self.annotator_id != other.annotator_id:
            return self.annotator_id < other.annotator_id
        if self.epoch_ticks != other.epoch_ticks:
            return self.epoch_ticks < other.epoch_ticks
        if self.rel_strength is not other.rel_strength:
            return self.rel_strength < other.rel_strength
        return False

    def __eq__(self, other):
        if self.content_id1 != other.content_id1:
            return False
        if self.content_id2 != other.content_id2:
            return False
        if self.annotator_id != other.annotator_id:
            return False
        if self.epoch_ticks != other.epoch_ticks:
            return False
        if self.rel_strength != other.rel_strength:
            return False
        return True

    def __hash__(self):
        return (hash(self.content_id1) ^
                hash(self.content_id2) ^
                hash(self.annotator_id) ^
                hash(self.epoch_ticks) ^
                hash(self.rel_strength))


class RelationLabelStore(object):
    '''A relation label database.

    .. automethod:: __init__
    .. automethod:: put
    .. automethod:: get
    .. automethod:: get_related
    .. automethod:: everything
    .. automethod:: delete_all
    '''

    TABLE = 'rel_label'
    config_name = 'relation_label_store'

    _kvlayer_namespace = {
        # (cid1, cid2, annotator_id, time) -> (rel_strength, meta)
        TABLE: (str, str, str, long),
    }

    def __init__(self, kvlclient):
        '''Create a new relation label store.
        '''
        self.kvl = kvlclient
        self.kvl.setup_namespace(self._kvlayer_namespace)

    def _keys_from_label(self, label):
        '''Convert a label into a kvl key.
        '''
        k1 = (label.content_id1, label.content_id2,
              label.annotator_id, time_complement(label.epoch_ticks))
        k2 = (label.content_id2, label.content_id1,
              label.annotator_id, time_complement(label.epoch_ticks))
        return k1, k2

    def _value_from_label(self, label):
        '''Convert a label into a kvl value.
        '''
        unser_val = (label.rel_strength.value, label.meta)
        return cbor.dumps(unser_val)

    def _label_from_kvlayer(self, key, val):
        '''Make a label from a kvlayer row.
        '''
        (content_id1, content_id2, annotator_id,
         inverted_epoch_ticks) = key
        epoch_ticks = time_complement(inverted_epoch_ticks)

        rel_strength, meta = cbor.loads(val)
        return RelationLabel(content_id1, content_id2, annotator_id,
                             RelationStrength(rel_strength),
                             epoch_ticks=epoch_ticks, meta=meta)

    def put(self, *labels):
        '''Add a new relation label to the store.
        '''
        puts = []
        for label in labels:
            k1, k2 = self._keys_from_label(label)
            v = self._value_from_label(label)
            puts.append((k1, v))
            puts.append((k2, v))
        self.kvl.put(self.TABLE, *puts)

    def get(self, cid1, cid2, annotator_id):
        '''Retrieve a relation label from the store.
        '''
        t = (cid1, cid2, annotator_id)
        for k, v in self.kvl.scan(self.TABLE, (t, t)):
            return self._label_from_kvlayer(k, v)

    def get_related(self, content_id, min_strength=None):
        '''Get positive relation labels for ``cid``.

        If ``min_strength`` is set, will restrict results to labels
        with a ``rel_strength`` greater or equal to the provided
        ``RelationStrength`` value. Note: ``min_strength`` should be of
        type ``RelationStrength``.
        '''
        def is_related(label):
            if min_strength is not None:
                return label.rel_strength >= min_strength
            else:
                return label.rel_strength.is_positive

        labels = self.everything(content_id=content_id)
        return ifilter(is_related, labels)

    def get_related_ids(self, content_id, min_strength=None):
        '''Get identifiers for related identifiers.
        '''
        related_labels = self.get_related(content_id,
                                          min_strength=min_strength)
        related_idents = set()
        for label in related_labels:
            related_idents.add(label.other(content_id))

        return list(related_idents)

    def get_relationships_for_idents(self, cid, idents):
        '''Get relationships between ``idents`` and a ``cid``.

        Returns a dictionary mapping the identifiers in ``idents``
        to either None, if no relationship label is found between
        the identifier and ``cid``, or a RelationshipType classifying
        the strength of the relationship between the identifier and
        ``cid``.
        '''
        keys = [(cid, ident,) for ident in idents]
        key_ranges = zip(keys, keys)
        mapping = {}
        for k, v in self.kvl.scan(self.TABLE, *key_ranges):
            label = self._label_from_kvlayer(k, v)
            ident = label.other(cid)
            rel_strength = label.rel_strength
            mapping[ident] = label.rel_strength

        return mapping

    def everything(self, content_id=None):
        '''Returns a generator of all labels in the store.

        If ``content_id`` is set, will restrict results to labels
        containing the provided ``content_id``.
        '''
        if content_id is not None:
            ranges = [((content_id,), (content_id,))]
        else:
            ranges = []

        labels = self.kvl.scan(self.TABLE, *ranges)
        labels = imap(lambda p: self._label_from_kvlayer(*p), labels)
        return labels

    def delete_all(self):
        '''Delete all labels in the store.
        '''
        self.kvl.clear_table(self.TABLE)
