# pylint:disable=no-self-use, unused-argument
from __future__ import absolute_import
from __future__ import unicode_literals

import os

import mock
import pytest

from pgctl import s6_poll_ready

pytestmark = pytest.mark.usefixtures('tmpdir')


class DescribeFloatFile(object):

    def it_loads_files(self):
        filename = 'notification-fd'
        with open(filename, 'w') as f:
            f.write('5')
        result = s6_poll_ready.floatfile(filename)
        assert isinstance(result, float)
        assert result == 5.0


class DescribeGetVal(object):

    def it_loads_environment_var(self):
        with mock.patch.dict(os.environ, [('SVWAIT', '5')]):
            result = s6_poll_ready.getval('', 'SVWAIT', '2')
            assert isinstance(result, float)
            assert result == 5.0

    def it_loads_file_var(self):
        with mock.patch.dict(os.environ, [('SVWAIT', '5')]):
            filename = 'notification-fd'
            with open(filename, 'w') as f:
                f.write('5')
            result = s6_poll_ready.getval('notification-fd', 'SVWAIT', 2)
            assert isinstance(result, float)
            assert result == 5.0

    def it_loads_default_var(self):
        result = s6_poll_ready.getval('', 'SVWAIT', '2')
        assert isinstance(result, float)
        assert result == 2.0


class DescribeS6PollReady(object):

    def it_times_out(self):
        with open('notification-file', 'w') as notification_file:
            fd = notification_file.fileno()
        with open('notification-fd', 'w') as notification_fd:
            notification_fd.write(str(fd))
        result = s6_poll_ready.s6_poll_ready(fd, 2, .1, lambda: 1)
        assert result == 'timed out.'