'''A simple storage interface for labels (ground truth data).

.. This software is released under an MIT/X11 open source license.
   Copyright 2012-2014 Diffeo, Inc.

:mod:`dossier.label` provides a convenient interface to a
:mod:`kvlayer` table for storing ground truth data, otherwise known as
"labels." Each label, at the highest level, maps two things (addressed
by content identifiers) to a coreferent value. This coreferent value is
an indication by a human that these two things are "the same", "not the
same" or "I don't know if they are the same." *Sameness* in this case
is determined by the human doing the annotation.

Each label also contains an ``annotator_id``, which identifies the
human that created the label. A timestamp (in milliseconds since the
Unix epoch) is also included on every label.

Example
-------
Using a storage backend in your code requires a working ``kvlayer``
configuration, which is usually written in a YAML file like so:

.. code-block:: yaml

    kvlayer:
      app_name: store
      namespace: dossier
      storage_type: redis
      storage_addresses: ["redis.example.com:6379"]

And here's a full working example that uses local memory to store
labels:

.. code-block:: python

    from dossier.label import Label, LabelStore, CorefValue
    import kvlayer
    import yakonfig

    yaml = """
    kvlayer:
      app_name: store
      namespace: dossier
      storage_type: local
    """
    with yakonfig.defaulted_config([kvlayer], yaml=yaml):
        label_store = LabelStore(kvlayer.client())

        lab = Label('a', 'b', 'annotator', CorefValue.Positive)
        label_store.put(lab)

        assert lab == label_store.get('a', 'b', 'annotator')

See the documentation for :mod:`yakonfig` for more details on the
configuration setup.

.. autoclass:: LabelStore
.. autoclass:: Label
.. autoclass:: CorefValue

:command:`dossier.label` command-line tool
==========================================

.. automodule:: dossier.label.run
'''
from __future__ import absolute_import, division, print_function

from dossier.label.label import Label, LabelStore, CorefValue, expand_labels
from dossier.label.relation_label import RelationLabel, RelationStrength, \
    RelationLabelStore

__all__ = ['Label', 'LabelStore', 'CorefValue', 'expand_labels']
