.. image:: https://badge.fury.io/py/mwpy.svg
    :target: https://badge.fury.io/py/mwpy
.. image:: https://travis-ci.org/5j9/mwpy.svg?branch=master
    :target: https://travis-ci.org/5j9/mwpy
.. image:: https://codecov.io/gh/5j9/mwpy/branch/master/graph/badge.svg
  :target: https://codecov.io/gh/5j9/mwpy

This is a personal pet project.
An ``async`` Python_ client for MediaWiki_ API built on top of asks_ and trio_!
Currently this project is abandoned in favour of pymw_, a synchronous fork of this project that uses requests.

Installation
------------
``mwpy`` requires Python 3.9+!

.. code-block::

    pip install mwpy


Notable features
----------------
- Supports setting a custom `User-Agent header`_ for each ``API`` instance.
- Handles `query continuations`_.
- Handles batchcomplete_ signals for prop queries and yeilds the results as soon as a batch is complete.
- Configurable maxlag_. Waits as the  API recommends and then retries.
- Some convenient methods for accessing common API calls, e.g. for recentchanges_, login_, and siteinfo_.
- Lightweight. ``mwpy`` is a thin wrapper. Method signatures are very similar to the parameters in an actual API URL. You can consult MediaWiki's documentation if in doubt about what a parameter does.

.. _MediaWiki: https://www.mediawiki.org/
.. _trio: https://github.com/python-trio/trio
.. _asks: https://github.com/theelous3/asks
.. _User-Agent header: https://www.mediawiki.org/wiki/API:Etiquette#The_User-Agent_header
.. _query continuations: https://www.mediawiki.org/wiki/API:Query#Example_4:_Continuing_queries
.. _batchcomplete: https://www.mediawiki.org/wiki/API:Query#Example_5:_Batchcomplete
.. _recentchanges: https://www.mediawiki.org/wiki/API:RecentChanges
.. _login: https://www.mediawiki.org/wiki/API:Login
.. _siteinfo: https://www.mediawiki.org/wiki/API:Siteinfo
.. _maxlag: https://www.mediawiki.org/wiki/Manual:Maxlag_parameter
.. _Python: https://www.python.org/
.. _pymw: https://github.com/5j9/pymw
