# -*- coding: utf-8 -*-

import re
import datetime
import os.path
import contextlib
import sys
import textwrap
from subprocess import Popen, PIPE

from kids.sh import ShellError, wrap
from kids.file import normpath, File
from kids.cache import cache


try:
    basestring  # attempt to evaluate basestring

    def isstr(s):
        return isinstance(s, basestring)
except NameError:

    def isstr(s):
        return isinstance(s, str)


@contextlib.contextmanager
def set_cwd(directory):
    curdir = os.getcwd()
    os.chdir(directory)
    try:
        yield
    finally:
        os.chdir(curdir)


WIN32 = sys.platform == 'win32'
if WIN32:
    PLT_CFG = {
        'close_fds': False,
    }
else:
    PLT_CFG = {
        'close_fds': True,
    }


class Proc(Popen):

    def __init__(self, command, env=None):
        super(Proc, self).__init__(
            command, stdin=PIPE, stdout=PIPE, stderr=PIPE,
            close_fds=PLT_CFG['close_fds'], env=env,
            universal_newlines=False)

        self.stdin = File(self.stdin)
        self.stdout = File(self.stdout)
        self.stderr = File(self.stderr)


class SubGitObjectMixin(object):

    def __init__(self, repos=None):
        if isstr(repos) or repos is None:
            repos = GitRepos(repos)
        self._repos = repos

    @property
    def git(self):
        """Simple delegation to ``repos`` original method."""
        return self._repos.git


GIT_FORMAT_KEYS = {
    'sha1': "%H",
    'sha1_short': "%h",
    'subject': "%s",
    'author_name': "%an",
    'author_email': "%ae",
    'author_date': "%ad",
    'author_date_timestamp': "%at",
    'committer_name': "%cn",
    'committer_date_timestamp': "%ct",
    'raw_body': "%B",
    'body': "%b",
    'parent_list_string': "%P",
    'decorate_string': "%D",
}

GIT_FULL_FORMAT_STRING = "%x00".join(GIT_FORMAT_KEYS.values())

REGEX_RFC822_KEY_VALUE = \
    r'(^|\n)(?P<key>[A-Z]\w+(-\w+)*): (?P<value>[^\n]*(\n\s+[^\n]*)*)'
REGEX_RFC822_POSTFIX = \
    r'(%s)+$' % REGEX_RFC822_KEY_VALUE


class GitCommit(SubGitObjectMixin):
    r"""Represent a Git Commit and expose through its attribute many information

    Let's create a fake GitRepos:

        >>> from minimock import Mock
        >>> repos = Mock("gitRepos")

    Initialization:

        >>> repos.git = Mock("gitRepos.git")
        >>> repos.git.log.mock_returns_func = \
        ...     lambda *a, **kwargs: "\x00".join([{
        ...             'sha1': "000000",
        ...             'sha1_short': "000",
        ...             'subject': SUBJECT,
        ...             'author_name': "John Smith",
        ...             'author_date': "Tue Feb 14 20:31:22 2017 +0700",
        ...             'author_email': "john.smith@example.com",
        ...             'author_date_timestamp': "0",   ## epoch
        ...             'committer_name': "Alice Wang",
        ...             'committer_date_timestamp': "0", ## epoch
        ...             'raw_body': "my subject\n\n%s" % BODY,
        ...             'body': BODY,
        ...             'parent_list_string': '',
        ...             'decorate_string': 'HEAD -> master, tag: 0.1.4, origin/master',
        ...         }[key] for key in GIT_FORMAT_KEYS.keys()])
        >>> repos.git.rev_list.mock_returns = "123456"

    Query, by attributes or items:

        >>> SUBJECT = "fee fie foh"
        >>> BODY = "foo foo foo"

        >>> head = GitCommit(repos, "HEAD")
        >>> head.subject
        Called gitRepos.git.log(...'HEAD'...)
        'fee fie foh'
        >>> head.author_name
        'John Smith'
        >>> list(head.parents)
        []
        >>> list(head.tags)
        Called gitRepos.git.rev_parse(['0.1.4^{tag}', '--'])
        [<GitTag '0.1.4' (annotated)>]

    Notice that on the second call, there's no need to call again git log as
    all the values have already been computed.

    Trailer
    =======

    ``GitCommit`` offers a simple direct API to trailer values. These
    are like RFC822's header value but are at the end of body:

        >>> BODY = '''\
        ... Stuff in the body
        ... Change-id: 1234
        ... Value-X: Supports multi
        ...   line values'''

        >>> head = GitCommit(repos, "HEAD")
        >>> head.trailer_change_id
        Called gitRepos.git.log(...'HEAD'...)
        '1234'
        >>> head.trailer_value_x
        'Supports multi\nline values'

    Notice how the multi-line value was unindented.
    In case of multiple values, these are concatened in lists:

        >>> BODY = '''\
        ... Stuff in the body
        ... Co-Authored-By: Bob
        ... Co-Authored-By: Alice
        ... Co-Authored-By: Jack
        ... '''

        >>> head = GitCommit(repos, "HEAD")
        >>> head.trailer_co_authored_by
        Called gitRepos.git.log(...'HEAD'...)
        ['Bob', 'Alice', 'Jack']


    Special values
    ==============

    Authors
    -------

        >>> BODY = '''\
        ... Stuff in the body
        ... Co-Authored-By: Bob
        ... Co-Authored-By: Alice
        ... Co-Authored-By: Jack
        ... '''

        >>> head = GitCommit(repos, "HEAD")
        >>> head.author_names
        Called gitRepos.git.log(...'HEAD'...)
        ['Alice', 'Bob', 'Jack', 'John Smith']

    Notice that they are printed in alphabetical order.

    """

    def __init__(self, repos, identifier):
        super(GitCommit, self).__init__(repos)
        self.identifier = identifier
        self._trailer_parsed = False

    def __getattr__(self, label):
        """Completes commits attributes upon request."""
        attrs = GIT_FORMAT_KEYS.keys()
        if label not in attrs:
            try:
                return self.__dict__[label]
            except KeyError:
                if self._trailer_parsed:
                    raise AttributeError(label)

        identifier = self.identifier

        ## Compute only missing information
        missing_attrs = [l for l in attrs if l not in self.__dict__]
        ## some commit can be already fully specified (see ``mk_commit``)
        if missing_attrs:
            aformat = "%x00".join(GIT_FORMAT_KEYS[l]
                                  for l in missing_attrs)
            try:
                ret = self.git.log([identifier, "--max-count=1",
                                   "--pretty=format:%s" % aformat, "--"])
            except ShellError:
                raise ValueError("Given commit identifier %r doesn't exists"
                                 % self.identifier)
            attr_values = ret.split("\x00")
            for attr, value in zip(missing_attrs, attr_values):
                setattr(self, attr, value.strip())

        ## Let's interpret RFC822-like header keys that could be in the body
        match = re.search(REGEX_RFC822_POSTFIX, self.body)
        if match is not None:
            pos = match.start()
            postfix = self.body[pos:]
            self.body = self.body[:pos]
            for match in re.finditer(REGEX_RFC822_KEY_VALUE, postfix):
                dct = match.groupdict()
                key = dct["key"].replace("-", "_").lower()
                if "\n" in dct["value"]:
                    first_line, remaining = dct["value"].split('\n', 1)
                    value = "%s\n%s" % (first_line,
                                        textwrap.dedent(remaining))
                else:
                    value = dct["value"]
                try:
                    prev_value = self.__dict__["trailer_%s" % key]
                except KeyError:
                    setattr(self, "trailer_%s" % key, value)
                else:
                    setattr(self, "trailer_%s" % key,
                            prev_value + [value, ]
                            if isinstance(prev_value, list)
                            else [prev_value, value, ])
        self._trailer_parsed = True
        return getattr(self, label)

    @property
    def author_names(self):
        return [re.sub(r'^([^<]+)<[^>]+>\s*$', r'\1', author).strip()
                for author in self.authors]

    @property
    def authors(self):
        co_authors = getattr(self, 'trailer_co_authored_by', [])
        co_authors = co_authors if isinstance(co_authors, list) \
                     else [co_authors]
        return sorted(co_authors +
                      ["%s <%s>" % (self.author_name, self.author_email)])

    @property
    def date(self):
        d = datetime.datetime.utcfromtimestamp(
            float(self.author_date_timestamp))
        return d.strftime('%Y-%m-%d')

    @property
    def parents(self):
        for sha1 in self.parents_sha1:
            c = self._repos.Commit(sha1)
            c.sha1 = sha1
            yield c

    @property
    def parents_sha1(self):
        for sha1 in self.parent_list_string.split(' '):
            if not sha1:
                continue
            yield sha1

    @property
    def tags_name(self):
        """Return list of tag names"""

        if self.decorate_string == "%D":  ## old version of git
            try:
                output = self._repos.git.tag(["-l", "--points-at", self.sha1])
            except ShellError:
                raise  ## unexpected errlvl
            return output.split('\n')

        tag_list = []
        for decoration in self.decorate_string.split(','):
            decoration = decoration.strip()
            if decoration.startswith('tag: '):
                tag_list.append(decoration[5:])
        return tag_list

    @property
    def tags(self):
        for tag_name in self.tags_name:
            yield GitTag(self._repos, tag_name)

    def tag(self, label):
        for tag in self.tags:
            if tag.label == label:
                return tag
        raise ValueError("No tag labelled %r in current commit."
                         % (label, ))

    def __le__(self, value):
        """Order notion between commit

        This is more-or-less comparable to the ``git log`` order
        output, ancestorship is first used, and if on parallel
        branches, using date order.  When date are equal, as a last
        resort, use sha1.

        """
        if not isinstance(value, GitCommit):
            value = self._repos.Commit(value)

        if self in value:
            return True

        try:
            self.git.merge_base(value.sha1, self.sha1)
        except ShellError:
            raise ValueError("Unrelated commits %r and %r."
                             % (self, value))

        if value in self:
            return False

        ## neither ``self`` nor ``value`` is ancestor of the other,
        ## they have a merge base, so they are in different branches
        ## so we need to check their tag dates
        if self.author_date_timestamp == value.author_date_timestamp:
            return self.sha1 <= value.sha1  ## arbitrary
        return self.author_date_timestamp <= value.author_date_timestamp

    def __lt__(self, value):
        if not isinstance(value, GitCommit):
            value = self._repos.Commit(value)
        return self <= value and self != value

    def __eq__(self, value):
        if not isinstance(value, GitCommit):
            value = self._repos.Commit(value)
        return self.sha1 == value.sha1

    def __contains__(self, value):
        if not isinstance(value, GitCommit):
            value = self._repos.Commit(value)
        try:
            self.git.merge_base("--is-ancestor", value.sha1, self.sha1)
            return True
        except ShellError as e:
            if e.errlvl != 1:
                raise
        return False

    def __hash__(self):
        return hash(self.sha1)

    def __repr__(self):
        return "<%s %r>" % (self.__class__.__name__, self.identifier)


class GitTag(SubGitObjectMixin):

    def __init__(self, repos, label):
        super(GitTag, self).__init__(repos)
        self.label = label

    @property
    def is_annotated(self):
        try:
            self.git.rev_parse(['%s^{tag}' % self.label, "--"])
            return True
        except ShellError as e:
            if e.errlvl != 128:
                raise
        return False

    @property
    def content(self):
        if self.is_annotated:
            return self.git.for_each_ref(
                'refs/tags/%s' % self.label, format='%(contents)')
        return None

    @property
    def date_timestamp(self):
        if self.is_annotated:
            date_utc = self.git.for_each_ref(
                'refs/tags/%s' % self.label, format='%(taggerdate:raw)')
            return date_utc.split(" ", 1)[0]
        return None

    @property
    def date(self):
        ts = self.date_timestamp
        if ts is None:
            return None
        d = datetime.datetime.utcfromtimestamp(float(ts))
        return d.strftime('%Y-%m-%d')

    @property
    def commit(self):
        return GitCommit(self._repos, self.identifier)

    def __repr__(self):
        return "<%s %r (%s)>" % (
            self.__class__.__name__,
            self.label,
            "annotated" if self.is_annotated else "lightweight")


class GitConfig(object):
    """Interface to config values of git

    Let's create a fake GitCmd:

        >>> from minimock import Mock
        >>> git = Mock("git")

    Initialization:

        >>> cfg = GitConfig(git_command=git)

    Query, by attributes or items:

        >>> git.config.mock_returns = "bar"
        >>> cfg.foo
        Called git.config('foo')
        'bar'
        >>> cfg["foo"]
        Called git.config('foo')
        'bar'
        >>> cfg.get("foo")
        Called git.config('foo')
        'bar'
        >>> cfg["foo.wiz"]
        Called git.config('foo.wiz')
        'bar'

    Notice that you can't use attribute search in subsection as ``cfg.foo.wiz``
    That's because in git config files, you can have a value attached to
    an element, and this element can also be a section.

    Nevertheless, you can do:

        >>> getattr(cfg, "foo.wiz")
        Called git.config('foo.wiz')
        'bar'

    Default values
    --------------

    get item, and getattr default values can be used:

        >>> del git.config.mock_returns
        >>> git.config.mock_raises = ShellError('Key not found',
        ...                                     outputs=("", "", 1))

        >>> getattr(cfg, "foo", "default")
        Called git.config('foo')
        'default'

        >>> cfg["foo"]  ## doctest: +ELLIPSIS
        Traceback (most recent call last):
        ...
        KeyError: 'foo'

        >>> getattr(cfg, "foo")  ## doctest: +ELLIPSIS
        Traceback (most recent call last):
        ...
        AttributeError...

        >>> cfg.get("foo", "default")
        Called git.config('foo')
        'default'

        >>> print("%r" % cfg.get("foo"))
        Called git.config('foo')
        None

    """

    def __init__(self, constrain_to_path=None, git_command=None):
        self._constrain_to_path = constrain_to_path
        self.git = git_command or GitCmd(self._constrain_to_path)

    def __getattr__(self, label):
        try:
            res = self.git.config(label)
        except ShellError as e:
            if e.errlvl == 1 and e.out == "":
                raise AttributeError("key %r is not found in git config."
                                     % label)
            raise
        return res

    def get(self, label, default=None):
        return getattr(self, label, default)

    def __getitem__(self, label):
        try:
            return getattr(self, label)
        except AttributeError:
            raise KeyError(label)


class GitCmd(object):

    def __init__(self, constrain_to_path=None):
        self._constrain_to_path = constrain_to_path

    def __getattr__(self, label):
        label = label.replace("_", "-")

        def dir_wrap(command, **kwargs):
            if self._constrain_to_path:
                with set_cwd(self._constrain_to_path):
                    return wrap(command, **kwargs)
            else:
                return wrap(command, **kwargs)

        def method(*args, **kwargs):
            if len(args) == 1 and not isstr(args[0]):
                return dir_wrap(
                    ['git', label, ] + args[0],
                    env=kwargs.get("env", None))
            cli_args = []
            for key, value in kwargs.items():
                cli_key = (("-%s" if len(key) == 1 else "--%s")
                           % key.replace("_", "-"))
                if isinstance(value, bool):
                    cli_args.append(cli_key)
                else:
                    cli_args.append(cli_key)
                    cli_args.append(value)

            cli_args.extend(args)

            return dir_wrap(['git', label, ] + cli_args)
        return method


class GitRepos(object):

    def __init__(self, path=None):

        if path is None:
            path = os.getcwd()

        ## Saving this original path to ensure all future git commands
        ## will be done from this location.
        self._orig_path = os.path.realpath(path)

        ## verify ``git`` command is accessible:
        try:
            self._git_version = self.git.version()
        except ShellError:
            raise EnvironmentError(
                "Required ``git`` command not found or broken in $PATH. "
                "(calling ``git version`` failed.)")

        try:
            self.git.remote()
        except ShellError:
            raise OSError(
                "Not a git repository (%r or any of the parent directories)."
                % self._orig_path)
    @cache
    @property
    def toplevel(self):
        return None if self.bare else self.git.rev_parse(show_toplevel=True)

    @cache
    @property
    def bare(self):
        return self.git.rev_parse(is_bare_repository=True) == "true"

    @cache
    @property
    def gitdir(self):
        return normpath(
            os.path.join(self._orig_path,
                         self.git.rev_parse(git_dir=True)))

    @property
    @cache
    def git(self):
        return GitCmd(self._orig_path)

    @classmethod
    def create(cls, directory, *args, **kwargs):
        os.mkdir(directory)
        return cls.init(directory, *args, **kwargs)

    @classmethod
    def init(cls, directory, name=None, email=None):
        with set_cwd(directory):
            wrap("git init .")
        self = cls(directory)
        if name:
            self.git.config("user.name", name)
        if email:
            self.git.config("user.email", email)
        return self

    def Tag(self, label):
        return GitTag(self, label)

    def Commit(self, identifier):
        return GitCommit(self, identifier)

    commit = Commit

    @cache
    @property
    def Config(self):
        return GitConfig(constrain_to_path=self._orig_path)

    config = Config

    @property
    def tags(self):
        """String list of repository's tag names

        Current tag order is committer date timestamp of tagged commit.
        No firm reason for that, and it could change in future version.

        """
        tags = self.git.tag().split("\n")
        ## Should we use new version name sorting ?  refering to :
        ## ``git tags --sort -v:refname`` in git version >2.0.
        ## Sorting and reversing with command line is not available on
        ## git version <2.0
        return sorted([self.Commit(tag) for tag in tags if tag != ''],
                      key=lambda x: int(x.committer_date_timestamp))

    def log(self, revlist=None, args=["--topo-order", ]):
        """Reverse chronological list of git repository's commits

        Note: rev lists can be GitCommit instance list or identifier list.

        """
        revlist = revlist or ["HEAD"]

        plog = Proc(
            ["git", "log", "--stdin", "-z",
             "--format=%s" % GIT_FULL_FORMAT_STRING] +
            args +
            (["--", ] if "--" not in args else []))

        for rev in revlist:
            plog.stdin.write("%s\n" % rev)

        plog.stdin.close()

        def mk_commit(dct):
            """Creates an already set commit from a dct"""
            c = self.Commit(dct["sha1"])
            for k, v in dct.items():
                setattr(c, k, v)
            return c

        values = plog.stdout.read("\x00")

        try:
            while True:  ## next(values) will eventualy raise StopIteration
                yield mk_commit({key: next(values) for key in GIT_FORMAT_KEYS})
        finally:
            plog.stdout.close()
            plog.stderr.close()
