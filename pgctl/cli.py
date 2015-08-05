# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import os
import time
from subprocess import CalledProcessError
from subprocess import PIPE
from subprocess import Popen

from cached_property import cached_property
from py._path.local import LocalPath as Path

from .config import Config
from .flock import flock
from .flock import Locked

PGCTL_DEFAULTS = {
    'pgdir': 'playground',
    'pgconf': 'conf.yaml',
    'services': ('default',),
}


def close_fds():
    """
    The builtin Popen close_fds doesn't close stdout, stderr,
    but we must in order to daemonize properly.
    """
    os.closerange(0, 3)  # close stdout et al to avoid deadlock when reading from parent

    # run our atexits before exec'ing our new process, to produce proper coverage reports.
    # in python3, sys.exitfunc has gone away, and atexit._run_exitfuncs seems to be the only pubic-ish interface
    #   https://hg.python.org/cpython/file/3.4/Modules/atexitmodule.c#l289
    import atexit
    atexit._run_exitfuncs()  # pragma:no cover pylint:disable=protected-access


def idempotent_svscan(pgdir):
    try:
        with flock(pgdir):
            Popen(('svscan', pgdir), preexec_fn=close_fds)
            # TODO: factor out this silly sleep.
            time.sleep(.1)  # pragma: no branch (see https://bitbucket.org/ned/coveragepy/issues/146)
    except Locked:
        return


class NoSuchService(Exception):
    pass


def svc(*args):
    # svc never writes to stdout.
    cmd = ('svc',) + tuple(args)
    p = Popen(cmd, stderr=PIPE)
    _, error = p.communicate()
    if 'unable to chdir' in error:
        raise NoSuchService(error)
    if p.returncode:  # pragma: no cover: there's no known way to hit this.
        import sys
        sys.stderr.write(error)
        raise CalledProcessError(p.returncode, cmd)


def svstat(*args):
    # svstat *always* exits with code zero...
    cmd = ('svstat',) + tuple(args)
    p = Popen(cmd, stdout=PIPE)
    status_group, _ = p.communicate()

    state_group = []
    #status is listed per line for each argument
    for status in status_group.splitlines():
        state_group.append(get_state(status))

    return state_group


def get_state(status):
    r"""
    Parse a single line of svstat output.

    >>> get_state("date: up (pid 1202562) 1 seconds\n")
    'up'

    >>> get_state("date: down 0 seconds, normally up, want up")
    'starting'

    >>> get_state("playground/date: down 0 seconds, normally up")
    'down'

    >>> get_state("date: up (pid 1202562) 1 seconds, want down\n")
    'stopping'
    """
    status = status.rstrip()
    if status.endswith(' want up'):
        state = 'starting'
    elif status.endswith(' want down'):
        state = 'stopping'
    else:
        _, status = status.split(':', 1)
        state, _ = status.split(None, 1)
    return str(state)


class PgctlApp(object):

    def __init__(self, config):
        self._config = config

    def __call__(self):
        # config guarantees this is set
        command = self._config['command']
        # argparse guarantees this is an attribute
        command = getattr(self, command)
        return command()

    def __change_state(self, opt, expected_state, xing, xed):
        print(xing, self.service)
        idempotent_svscan(self.pgdir.strpath)
        with self.pgdir.as_cwd():
            # TODO-TEST: it can {start,stop} multiple services at once
            try:
                while True:  # a poor man's do/while
                    svc(opt, *self.service)
                    if all(state == expected_state for state in svstat(*self.service)):
                        break
                    else:
                        time.sleep(.01)
                print(xed, self.service)
            except NoSuchService:
                return "No such playground service: '%s'" % self.service

    def start(self):
        return self.__change_state('-u', 'up', 'Starting:', 'Started:')

    def stop(self):
        return self.__change_state('-d', 'down', 'Stopping:', 'Stopped:')

    def status(self):
        print('Status:', self.service)

    def restart(self):
        self.stop()
        self.start()

    def reload(self):
        print('reload:', self._config['services'])

    def log(self):
        print('Log:', self._config['services'])

    def debug(self):
        print('Debugging:', self._config['services'])

    def config(self):
        import json
        print(json.dumps(self._config, sort_keys=True, indent=4))

    @cached_property
    def service(self):
        if self._config['services'][0] == 'default':
            return [
                service.basename
                for service in self.pgdir.listdir()
                if service.check(dir=True)
            ]
        else:
            return self._config['services']

    @cached_property
    def pgdir(self):
        return Path(self._config['pgdir'])

    commands = (start, stop, status, restart, reload, log, debug, config)


def parser():
    commands = [command.__name__ for command in PgctlApp.commands]
    parser = argparse.ArgumentParser()
    parser.add_argument('--pgdir', help='name the playground directory', default=argparse.SUPPRESS)
    parser.add_argument('--pgconf', help='name the playground config file', default=argparse.SUPPRESS)
    parser.add_argument('command', help='specify what action to take', choices=commands, default=argparse.SUPPRESS)
    parser.add_argument('services', nargs='*', help='specify which services to act upon', default=argparse.SUPPRESS)

    return parser


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    config = Config('pgctl')
    config = config.combined(PGCTL_DEFAULTS, args)
    app = PgctlApp(config)

    return app()


if __name__ == '__main__':
    exit(main())
