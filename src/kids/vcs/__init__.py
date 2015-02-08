# Package placeholder

import datetime
import os.path
from subprocess import Popen, PIPE


from kids.txt import indent
from kids.sh import ShellError, ShellOutput, swrap
from kids.file import normpath, File
from kids.cache import cache


try:
    basestring  # attempt to evaluate basestring

    def isstr(s):
        return isinstance(s, basestring)
except NameError:

    def isstr(s):
        return isinstance(s, str)


class SubGitObjectMixin(object):

    def __init__(self, repos=None):
        if isstr(repos) or repos is None:
            repos = GitRepos(repos)
        self._repos = repos

    def swrap(self, *args, **kwargs):
        """Simple delegation to ``repos`` original method."""
        return self._repos.swrap(*args, **kwargs)


GIT_FORMAT_KEYS = {
    'sha1': "%H",
    'subject': "%s",
    'author_name': "%an",
    'author_date': "%ad",
    'author_date_timestamp': "%at",
    'committer_name': "%cn",
    'committer_date_timestamp': "%ct",
    'raw_body': "%B",
    'body': "%b",
}

GIT_FULL_FORMAT_STRING = "%x00".join(GIT_FORMAT_KEYS.values())


class GitCommit(SubGitObjectMixin):

    def __init__(self, repos, identifier):
        super(GitCommit, self).__init__(repos)
        self.identifier = identifier

    def __getattr__(self, label):
        """Completes commits attributes upon request."""
        attrs = GIT_FORMAT_KEYS.keys()
        if label not in attrs:
            return super(GitCommit, self).__getattr__(label)

        identifier = self.identifier
        if identifier == "LAST":
            identifier = self.swrap(
                "git rev-list --first-parent --max-parents=0 HEAD")

        ## Compute only missing information
        missing_attrs = [l for l in attrs if l not in self.__dict__]
        aformat = "%x00".join(GIT_FORMAT_KEYS[l]
                              for l in missing_attrs)
        try:
            ret = self.swrap("git show -s %s --pretty=format:%s --"
                             % (identifier, aformat))
        except ShellError:
            raise ValueError("Given commit identifier %s doesn't exists"
                             % self.identifier)
        attr_values = ret.split("\x00")
        for attr, value in zip(missing_attrs, attr_values):
            setattr(self, attr, value.strip())
        return getattr(self, label)

    @property
    def date(self):
        d = datetime.datetime.utcfromtimestamp(
            float(self.author_date_timestamp))
        return d.strftime('%Y-%m-%d')

    def __eq__(self, value):
        if not isinstance(value, GitCommit):
            return False
        return self.sha1 == value.sha1

    def __hash__(self):
        return hash(self.sha1)

    def __repr__(self):
        return "<%s %r>" % (self.__class__.__name__, self.identifier)


class GitConfig(SubGitObjectMixin):
    """Interface to config values of git

    Let's create a fake GitRepos:

        >>> from minimock import Mock
        >>> repos = Mock("gitRepos")

    Initialization:

        >>> cfg = GitConfig(repos)

    Query, by attributes or items:

        >>> repos.swrap.mock_returns = "bar"
        >>> cfg.foo
        Called gitRepos.swrap("git config 'foo'")
        'bar'
        >>> cfg["foo"]
        Called gitRepos.swrap("git config 'foo'")
        'bar'
        >>> cfg.get("foo")
        Called gitRepos.swrap("git config 'foo'")
        'bar'
        >>> cfg["foo.wiz"]
        Called gitRepos.swrap("git config 'foo.wiz'")
        'bar'

    Notice that you can't use attribute search in subsection as ``cfg.foo.wiz``
    That's because in git config files, you can have a value attached to
    an element, and this element can also be a section.

    Nevertheless, you can do:

        >>> getattr(cfg, "foo.wiz")
        Called gitRepos.swrap("git config 'foo.wiz'")
        'bar'

    Default values
    --------------

    get item, and getattr default values can be used:

        >>> del repos.swrap.mock_returns
        >>> repos.swrap.mock_raises = ShellError(
        ...     'Key not found',
        ...     outputs=ShellOutput(errlvl=1, out="", err=""))

        >>> cfg["foo"]  ## doctest: +ELLIPSIS
        Traceback (most recent call last):
        ...
        KeyError: 'foo'

        >>> cfg.foo  ## doctest: +ELLIPSIS
        Traceback (most recent call last):
        ...
        AttributeError...

        >>> getattr(cfg, "foo", "default")
        Called gitRepos.swrap("git config 'foo'")
        'default'

        >>> cfg.get("foo", "default")
        Called gitRepos.swrap("git config 'foo'")
        'default'

        >>> print("%r" % cfg.get("foo"))
        Called gitRepos.swrap("git config 'foo'")
        None

    """

    def __init__(self, repos=None):
        super(GitConfig, self).__init__(repos=repos)

    def __getattr__(self, label):
        cmd = "git config %r" % str(label)
        try:
            res = self.swrap(cmd)
        except ShellError as e:
            out, err, errlvl = e.outputs
            if errlvl == 1 and out == "" and err == "":
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


def repos_cmd(f):

    def _f(self, *a, **kw):
        ## verify that we are in a git repository
        try:
            self.swrap("git remote")
        except ShellError:
            raise OSError(
                "Not a git repository (%r or any of the parent directories)."
                % self._orig_path)
        return f(self, *a, **kw)
    return _f


class GitRepos(object):

    def __init__(self, path=None):

        if path is None:
            path = os.getcwd()

        ## Saving this original path to ensure all future git commands
        ## will be done from this location.
        self._orig_path = os.path.realpath(path)

        ## verify ``git`` command is accessible:
        try:
            self._git_version = self.swrap("git version")
        except ShellError:
            raise EnvironmentError(
                "Required ``git`` command not found or broken in $PATH. "
                "(calling ``git version`` failed.)")

    @cache
    @property
    @repos_cmd
    def toplevel(self):
        return None if self.bare else \
               self.swrap("git rev-parse --show-toplevel")

    @cache
    @property
    @repos_cmd
    def bare(self):
        return self.swrap("git rev-parse --is-bare-repository") == "true"

    @cache
    @property
    @repos_cmd
    def gitdir(self):
        return normpath(
            os.path.join(self._orig_path,
                         self.swrap("git rev-parse --git-dir")))

    @repos_cmd
    def commit(self, identifier):
        return GitCommit(self, identifier)

    @cache
    @property
    def config(self):
        return GitConfig(self)

    def swrap(self, command, **kwargs):
        """Essential force the CWD of the command to be in self._orig_path"""

        command = "cd %s; %s" % (self._orig_path, command)
        return swrap(command, **kwargs)

    @property
    @repos_cmd
    def tags(self):
        """String list of repository's tag names

        Current tag order is committer date timestamp of tagged commit.
        No firm reason for that, and it could change in future version.

        """
        tags = self.swrap('git tag -l').split("\n")
        ## Should we use new version name sorting ?  refering to :
        ## ``git tags --sort -v:refname`` in git version >2.0.
        ## Sorting and reversing with command line is not available on
        ## git version <2.0
        return sorted([self.commit(tag) for tag in tags if tag != ''],
                      key=lambda x: int(x.committer_date_timestamp))

    @repos_cmd
    def log(self, includes=["HEAD", ], excludes=[], include_merge=True):
        """Reverse chronological list of git repository's commits

        Note: rev lists can be GitCommit instance list or identifier list.

        """

        refs = {'includes': includes,
                'excludes': excludes}
        for ref_type in ('includes', 'excludes'):
            for idx, ref in enumerate(refs[ref_type]):
                if not isinstance(ref, GitCommit):
                    refs[ref_type][idx] = self.commit(ref)

        ## --topo-order: don't mix commits from separate branches.
        command = (
            "cd %s; git log --stdin -z --topo-order --pretty=format:%s %s --"
            % (self._orig_path,
               GIT_FULL_FORMAT_STRING,
               '--no-merges' if not include_merge else ''))
        plog = Popen(command, shell=True,
                     stdin=PIPE, stdout=PIPE, stderr=PIPE,
                     close_fds=True, env=None,
                     universal_newlines=False)
        try:
            ## unicode convertion on (compat PY2 and PY3)
            plog.stdin = File(plog.stdin)
            for ref in refs["includes"]:
                plog.stdin.write("%s\n" % ref.sha1)

            for ref in refs["excludes"]:
                plog.stdin.write("^%s\n" % ref.sha1)
            plog.stdin.close()
        except IOError:
            errlvl = plog.poll()
            if errlvl is not None:  ## it has returned too early
                out = '\n'.join(File(plog.stdout).read())
                err = '\n'.join(File(plog.stderr).read())
                raise ShellError(
                    "Git call unexpetedly failed before end of stdin.",
                    command=command,
                    outputs=ShellOutput(out, err, errlvl))
            raise

        def mk_commit(dct):
            """Creates an already set commit from a dct"""
            c = self.commit(dct["sha1"])
            for k, v in dct.items():
                setattr(c, k, v)
            return c

        values = File(plog.stdout).read("\x00")

        try:
            while True:  ## values.next() will eventualy raise a StopIteration
                yield mk_commit(dict([(key, next(values))
                                      for key in GIT_FORMAT_KEYS]))
        finally:
            plog.stdout.close()
            plog.stderr.close()
