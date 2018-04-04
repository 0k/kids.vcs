=========================
kids.vcs
=========================

.. image:: http://img.shields.io/pypi/v/kids.vcs.svg?style=flat
   :target: https://pypi.python.org/pypi/kids.vcs/
   :alt: Latest PyPI version

.. image:: http://img.shields.io/pypi/dm/kids.vcs.svg?style=flat
   :target: https://pypi.python.org/pypi/kids.vcs/
   :alt: Number of PyPI downloads

.. image:: http://img.shields.io/travis/0k/kids.vcs/master.svg?style=flat
   :target: https://travis-ci.org/0k/kids.vcs/
   :alt: Travis CI build status

.. image:: http://img.shields.io/coveralls/0k/kids.vcs/master.svg?style=flat
   :target: https://coveralls.io/r/0k/kids.vcs
   :alt: Test coverage



``kids.vcs`` is a Python library providing GIT helpers. Would have
named it ``kids.git`` if it didn't messed everything with github.

It's part of 'Kids' (for Keep It Dead Simple) library.


Features
========

using ``kids.vcs``:

- You can manage and access your git repository, commits, logs, or git
  config.

Compatibility
=============

Tis code is python2 and python3 ready. It wasn't tested on windows.


Installation
============

You don't need to download the GIT version of the code as ``kids.vcs`` is
available on the PyPI. So you should be able to run::

    pip install kids.vcs

If you have downloaded the GIT sources, then you could add install
the current version via traditional::

    python setup.py install

And if you don't have the GIT sources but would like to get the latest
master or branch from github, you could also::

    pip install git+https://github.com/0k/kids.vcs

Or even select a specific revision (branch/tag/commit)::

    pip install git+https://github.com/0k/kids.vcs@master


Usage
=====

Let's play with a new git repository, let's first create temporary
directory::

    >>> from __future__ import print_function

    >>> import tempfile, os
    >>> old_cwd = os.getcwd()
    >>> tmpdir = tempfile.mkdtemp()
    >>> os.chdir(tmpdir)

Let's now create a real git repository::

    >>> from kids.sh import wrap

    >>> _ = wrap("""
    ...
    ...     ## Creating repository
    ...     mkdir repos
    ...     cd repos
    ...     git init .
    ...
    ...     git config user.email "committer@example.com"
    ...     git config user.name "The Committer"
    ...
    ... """)

We can now already access it::

    >>> from kids.vcs import GitRepos

    >>> r = GitRepos("repos")

By default, the current directory is used and the top-most git repository
that contains the current directory will be used as the master git repository.


Access core informations
------------------------

You can get interesting information fron the git repository itself::

    >>> print(r.toplevel)
    /.../repos

    >>> r.bare
    False

    >>> print(r.gitdir)
    /.../repos/.git


Read git config
---------------

We can access the config thanks to::

    >>> r.config
    <...GitConfig...>

    >>> print(r.config["core.filemode"])
    true

You can also instanciate directly the ``GitConfig`` class::

    >>> from kids.vcs import GitConfig

    >>> print(GitConfig("repos")["core.filemode"])
    true

Without any repository, it's the current repository that should be
used, and if none, well it should answer as much as a normal ``git
config`` would::

    >>> GitConfig()["core.filemode"]
    Traceback (most recent call last):
    ...
    KeyError: 'core.filemode'
    >>> os.chdir("repos")
    >>> print(GitConfig()["core.filemode"])
    true


Git commit access
-----------------

We can access interesting information per commit, for the following
we need actually to commit something::

    >>> _ = wrap(r"""
    ...     cd repos
    ...     ## Adding first file
    ...     echo 'Hello' > a
    ...     git add a
    ...     git commit -m 'new: first commit' \
    ...         --author 'Bob <bob@example.com>' \
    ...         --date '2000-01-01 10:00:00'
    ...     git tag 0.0.1
    ...
    ...     ## Adding second file
    ...     echo 'Second file' > b
    ...     git add b
    ...
    ...     ## Notice there are no section here.
    ...     git commit -m 'added ``b``, what a summary !' \
    ...         --author 'Alice <alice@example.com>' \
    ...         --date '2000-01-02 11:00:00'
    ...     git tag 0.0.2
    ... """)

Now we can::

    >>> r.commit("HEAD")
    <GitCommit 'HEAD'>

And several informations are available::

    >>> print(r.commit("HEAD").author_name)
    Alice
    >>> print(r.commit("master").subject)
    added ``b``, what a summary !

You can access to all of these::

    >>> from kids.vcs import GIT_FORMAT_KEYS

    >>> print(", ".join(sorted(GIT_FORMAT_KEYS)))
    author_date, author_date_timestamp, author_name, body,
    committer_date_timestamp, committer_name, raw_body, sha1, subject


There's a convienience attribute ``date`` also::

    >>> print(r.commit("0.0.2").date)
    2000-01-02


Tags
----

You can get the list of tags::

    >>> r.tags
    [<GitCommit ...'0.0.1'>, <GitCommit ...'0.0.2'>]


Logs
----

You can access all commits via::

    >>> list(r.log())
    [<GitCommit ...>, <GitCommit ...>]

and provide wich commit ancestry to include or to exclude (see ``git
log``)::

    >>> list(r.log(includes=["HEAD", ], excludes=["0.0.1", ]))
    [<GitCommit ...>]

Avoid doing this on a non-existent repository::

    >>> list(GitRepos("/").log())
    Traceback (most recent call last):
    ...
    OSError: Not a git repository ('/' or any of the parent directories).



Contributing
============

Any suggestion or issue is welcome. Push request are very welcome,
please check out the guidelines.


Push Request Guidelines
-----------------------

You can send any code. I'll look at it and will integrate it myself in
the code base and leave you as the author. This process can take time and
it'll take less time if you follow the following guidelines:

- check your code with PEP8 or pylint. Try to stick to 80 columns wide.
- separate your commits per smallest concern.
- each commit should pass the tests (to allow easy bisect)
- each functionality/bugfix commit should contain the code, tests,
  and doc.
- prior minor commit with typographic or code cosmetic changes are
  very welcome. These should be tagged in their commit summary with
  ``!minor``.
- the commit message should follow gitchangelog rules (check the git
  log to get examples)
- if the commit fixes an issue or finished the implementation of a
  feature, please mention it in the summary.

If you have some questions about guidelines which is not answered here,
please check the current ``git log``, you might find previous commit that
would show you how to deal with your issue.


License
=======

Copyright (c) 2018 Valentin Lab.

Licensed under the `BSD License`_.

.. _BSD License: http://raw.github.com/0k/kids.vcs/master/LICENSE
