
from __future__ import absolute_import
from __future__ import division

import collections
import datetime
import logging

import vaping
from vaping.io import subprocess
from vaping.util import which


class FPingBase(vaping.plugins.TimedProbe):
    """
    FPing base plugin

    config:
        `command` command to run
        `interval` time between pings
        `count` number of pings to send
    """

    default_config = {
        'command': 'fping',
        'interval': '1m',
        'count': 5,
    }

    def __init__(self, config, ctx):
        super(FPingBase, self).__init__(config, ctx)

        if not which(self.pluginmgr_config['command']):
            self.log.critical("missing fping, install it or set `command` in the fping config")
            raise RuntimeError("fping command not found")

        self.count = int(self.pluginmgr_config.get('count', 0))

    def hosts_args(self):
        """
        hosts list can contain strings specifying a host directly
        or dicts containing a "host" key to specify the host

        this way we can allow passing further config details (color, name etc.)
        with each host as well as simply dropping in addresses for quick
        setup depending on the user's needs
        """

        host_args = []
        for row in self.hosts:
            if isinstance(row, dict):
                host_args.append(row["host"])
            else:
                host_args.append(row)
        return list(set(host_args))

    def parse_verbose(self, line):
        """
        parse output from verbose format
        """
        try:
            logging.debug(line)
            (host, pings) = line.split(':')
            cnt = 0
            lost = 0
            times = []
            pings = pings.strip().split(' ')
            cnt = len(pings)
            for latency in pings:
                if latency == '-':
                    continue
                times.append(float(latency))

            lost = cnt - len(times)
            if lost:
                loss = lost / float(cnt)
            else:
                loss = 0.0

            rv = {
                'host': host.strip(),
                'cnt': cnt,
                'loss': loss,
                'data': times,
                }
            if times:
                rv['min'] = min(times)
                rv['max'] = max(times)
                rv['avg'] = sum(times) / len(times)
            return rv

        except Exception as e:
            logging.error("failed to get data {}".format(e))

    def _run_send(self, args):
        # get both stdout and stderr
        proc = self.popen(args, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)

        msg = {}
        msg['data'] = []
        msg['type'] = self.__class__.plugin_type
        msg['source'] = self.name
        msg['ts'] = (datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)).total_seconds()

        # TODO poll, timeout, maybe from parent process for better control?
        with proc.stdout:
            for line in iter(proc.stdout.readline, b''):
                line = line.decode("utf-8")
                msg['data'].append(self.parse_verbose(line))

        return msg


@vaping.plugin.register('fping')
class FPing(FPingBase):
    """
    Run fping on configured hosts

    config:
        `command` command to run
        `interval` time between pings
        `count` number of pings to send
    """

    def init(self):
        self.hosts = []
        for k, v in list(self.pluginmgr_config.items()):
            # dict means it's a group
            if isinstance(v, collections.Mapping):
                self.hosts.extend(v['hosts'])

    def probe(self):
        args = [
            self.pluginmgr_config['command'],
            '-u',
            '-C%d' % self.count,
            '-p20',
            '-e'
        ]
        args.extend(self.hosts_args())

        return self._run_send(args)
