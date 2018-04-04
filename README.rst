=========================
kids.vcs
=========================

.. image:: http://img.shields.io/pypi/v/kids.vcs.svg?style=flat
   :target: https://pypi.python.org/pypi/kids.vcs/
   :alt: Latest PyPI version

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

    >>> from kids.vcs import git

This first command will create a new directory and launch ``git init`` and
and will return the new ``GitRepos`` object::

    >>> r = git.GitRepos.create("repos",
    ...                         email="committer@example.com",
    ...                         name="The Committer")

You might also want to only use an existing directory and launch ``git init`` then
use::

    >>> r = git.GitRepos.init("repos")

Or, if wanting to use an already existing folder already initialised::

    >>> r = git.GitRepos("repos")

By default, the current directory is used and the top-most git repository
that contains the current directory will be used as the master git repository.

Avoid instantiating a non-existent git repository::

    >>> git.GitRepos("/")
    Traceback (most recent call last):
    ...
    OSError: Not a git repository ('/' or any of the parent directories).



Git commands shortcut
---------------------

Aside from all the helpers that will be exposed in the following section, a
``GitRepos`` object provides a handy ``.git`` attribute to directly tap on
the git command line::

    >>> print(r.git.rev_parse(is_bare_repository=True))
    false

A few things to note:

- the method name is the git command you want to launch
- ``_`` (underscores) are swapped for ``-``.
- there are 2 different way to use the methods:

  - provide one unique array of strings that will simply appended
    on the command line.

  - provide string positional arguments and keyword arguments:

    - keyword arguments are options... :

      - a double-dash will be added before the keyword if it is
        composed of more than one char
      - a single dash will be added before the keyword in cas it
        a single character keyword.
      - ``_`` (underscores) are swapped for ``-`` in keyword name
      - and value is appended just after on the command line.

    - positional arguments are appended AFTER all the options...

- the method return value is the space-stripped standard output of the
  command sent.

To illustrate this and the following points::

    >>> print(r.git.commit(
    ...     message='new: first commit',
    ...     author='Bob <bob@example.com>',
    ...     date='2000-01-01 10:00:00',
    ...     allow_empty=True))
    [master (root-commit) ...] new: first commit
     Author: Bob <bob@example.com>
     Date: Sat Jan 1 10:00:00 2000 ...

    >>> print(r.git.tag("0.0.1"))
    >>> print(r.git.commit(
    ...     message='new: second commit',
    ...     author='Alice <alice@example.com>',
    ...     date='2000-01-02 11:00:00',
    ...     allow_empty=True))
    [master ...] new: second commit
     Author: Alice <alice@example.com>
     Date: Sun Jan 2 11:00:00 2000 ...
    >>> print(r.git.tag("0.0.2"))


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

    >>> from kids.vcs import git

    >>> print(git.GitConfig("repos")["core.filemode"])
    true

Without any repository, it's the current repository that should be
used, and if none, well it should answer as much as a normal ``git
config`` would::

    >>> git.GitConfig()["core.filemode"]
    Traceback (most recent call last):
    ...
    KeyError: 'core.filemode'
    >>> os.chdir("repos")
    >>> print(git.GitConfig()["core.filemode"])
    true


Git commit access
-----------------

We can access interesting information per commit::

    >>> r.commit("HEAD")
    <GitCommit 'HEAD'>

And several information are available::

    >>> print(r.commit("HEAD").author_name)
    Alice
    >>> print(r.commit("master").subject)
    new: second commit

You can access to all of these::

    >>> print(", ".join(sorted(git.GIT_FORMAT_KEYS)))
    author_date, author_date_timestamp, author_email, author_name, body,
    committer_date_timestamp, committer_name, decorate_string,
    parent_list_string, raw_body, sha1, sha1_short, subject


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

    >>> list(r.log(["HEAD", "^0.0.1", ]))
    [<GitCommit ...>]


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
