#!/usr/bin/env python3

import os
from os import path
import sys
import time
import uuid
import random
import signal
import traceback
from subprocess import PIPE
from collections import namedtuple

import arg_parser
import context
from helpers import utils, kernel_ctl
from helpers.subprocess_wrappers import Popen, call

Flow = namedtuple('Flow', ['cc', 'cc_src_local', 'cc_src_remote', 'run_first', 'run_second'])


class Test(object):
    def __init__(self, args, run_id, cc):
        self.mode = args.mode
        self.run_id = run_id
        self.cc = cc
        self.data_dir = path.abspath(args.data_dir)

        self.flows = args.flows
        self.runtime = args.runtime
        self.interval = args.interval
        self.run_times = args.run_times

        self.proc_first = None
        self.proc_second = None
        self.ts_manager = None
        self.tc_manager = None
        self.test_start_time = None
        self.test_end_time = None

        if self.mode == 'local':
            self.datalink_trace = args.uplink_trace
            self.acklink_trace = args.downlink_trace
            self.prepend_mm_cmds = args.prepend_mm_cmds
            self.append_mm_cmds = args.append_mm_cmds
            self.extra_mm_link_args = args.extra_mm_link_args
            self.sender_side = 'remote'
            self.server_side = 'local'

        if self.mode == 'remote':
            self.sender_side = args.sender_side
            self.server_side = args.server_side
            self.local_addr = args.local_addr
            self.local_if = args.local_if
            self.remote_if = args.remote_if
            self.local_desc = args.local_desc
            self.remote_desc = args.remote_desc
            self.ntp_addr = args.ntp_addr
            self.local_ofst = None
            self.remote_ofst = None
            self.r = utils.parse_remote_path(args.remote_path, self.cc)

        self.test_config = getattr(args, 'test_config', None)

        if self.test_config:
            self.cc = self.test_config['test-name']
            self.flow_objs = {}
            cc_src_remote_dir = self.r['base_dir'] if self.mode == 'remote' else ''
            tun_id = 1
            for flow in self.test_config['flows']:
                cc = flow['scheme']
                run_first, run_second = utils.who_runs_first(cc)
                local_p = path.join(context.src_dir, 'wrappers', cc + '.py')
                remote_p = path.join(cc_src_remote_dir, 'wrappers', cc + '.py')
                self.flow_objs[tun_id] = Flow(cc, local_p, remote_p, run_first, run_second)
                tun_id += 1

    def setup(self):
        self.cc_src = path.join(context.src_dir, 'wrappers', self.cc + '.py')
        self.tunnel_manager = path.join(context.src_dir, 'experiments', 'tunnel_manager.py')
        self.run_first, self.run_second = utils.who_runs_first(self.cc) if not self.test_config else (None, None)
        self.run_first_setup_time = 3
        self.datalink_name = f'{self.cc}_datalink_run{self.run_id}'
        self.acklink_name = f'{self.cc}_acklink_run{self.run_id}'
        self.datalink_log = path.join(self.data_dir, self.datalink_name + '.log')
        self.acklink_log = path.join(self.data_dir, self.acklink_name + '.log')

        if self.mode == 'local':
            self.mm_datalink_log = path.join(self.data_dir, f'{self.cc}_mm_datalink_run{self.run_id}.log')
            self.mm_acklink_log = path.join(self.data_dir, f'{self.cc}_mm_acklink_run{self.run_id}.log')
            uplink_log = self.mm_datalink_log if self.run_first == 'receiver' else self.mm_acklink_log
            downlink_log = self.mm_acklink_log if self.run_first == 'receiver' else self.mm_datalink_log
            uplink_trace = self.datalink_trace if self.run_first == 'receiver' else self.acklink_trace
            downlink_trace = self.acklink_trace if self.run_first == 'receiver' else self.datalink_trace

            self.mm_cmd = []
            if self.prepend_mm_cmds:
                self.mm_cmd += self.prepend_mm_cmds.split()
            self.mm_cmd += [
                'mm-link', uplink_trace, downlink_trace,
                f'--uplink-log={uplink_log}',
                f'--downlink-log={downlink_log}'
            ]
            if self.extra_mm_link_args:
                self.mm_cmd += self.extra_mm_link_args.split()
            if self.append_mm_cmds:
                self.mm_cmd += self.append_mm_cmds.split()

    def run_without_tunnel(self):
        port = utils.get_open_port()
        cmd = ['python', self.cc_src, self.run_first, port]
        sys.stderr.write(f'Running {self.cc} {self.run_first}...\n')
        self.proc_first = Popen(cmd, preexec_fn=os.setsid)
        time.sleep(self.run_first_setup_time)
        self.test_start_time = utils.utc_time()

        sh_cmd = f'python {self.cc_src} {self.run_second} $MAHIMAHI_BASE {port}'
        sh_cmd = ' '.join(self.mm_cmd) + f" -- sh -c '{sh_cmd}'"
        sys.stderr.write(f'Running {self.cc} {self.run_second}...\n')
        self.proc_second = Popen(sh_cmd, shell=True, preexec_fn=os.setsid)

        signal.signal(signal.SIGALRM, utils.timeout_handler)
        signal.alarm(self.runtime)

        try:
            self.proc_first.wait()
            self.proc_second.wait()
        except utils.TimeoutError:
            pass
        else:
            signal.alarm(0)
            sys.stderr.write('Warning: test exited before time limit\n')
        finally:
            self.test_end_time = utils.utc_time()

        return True

    def run_tunnel_managers(self):
        ts_cmd = ['python3', self.tunnel_manager]
        sys.stderr.write('[tunnel server manager (tsm)] ')
        self.ts_manager = Popen(ts_cmd, stdin=PIPE, stdout=PIPE, preexec_fn=os.setsid)

        while True:
            running = self.ts_manager.stdout.readline()
            if b'tunnel manager is running' in running:
                sys.stderr.write(running.decode())
                break

        self.ts_manager.stdin.write(b'prompt [tsm]\n')
        self.ts_manager.stdin.flush()

        tc_cmd = self.mm_cmd + ['python3', self.tunnel_manager]
        sys.stderr.write('[tunnel client manager (tcm)] ')
        self.tc_manager = Popen(tc_cmd, stdin=PIPE, stdout=PIPE, preexec_fn=os.setsid)

        while True:
            running = self.tc_manager.stdout.readline()
            if b'tunnel manager is running' in running:
                sys.stderr.write(running.decode())
                break

        self.tc_manager.stdin.write(b'prompt [tcm]\n')
        self.tc_manager.stdin.flush()

        return self.ts_manager, self.tc_manager

    def run_with_tunnel(self):
        ts_manager, tc_manager = self.run_tunnel_managers()
        # This part should be expanded for actual tunnel flow setup logic...
        return True

    def run_congestion_control(self):
        try:
            return self.run_with_tunnel() if self.flows > 0 else self.run_without_tunnel()
        finally:
            utils.kill_proc_group(self.ts_manager if self.flows > 0 else self.proc_first)
            utils.kill_proc_group(self.tc_manager if self.flows > 0 else self.proc_second)

    def run(self):
        sys.stderr.write(f'Testing scheme {self.cc} for experiment run {self.run_id}/{self.run_times}...\n')
        self.setup()
        if not self.run_congestion_control():
            sys.stderr.write(f'Error in testing scheme {self.cc} with run ID {self.run_id}\n')
            return
        sys.stderr.write(f'Done testing {self.cc}\n')


def run_tests(args):
    git_summary = utils.get_git_summary(args.mode, getattr(args, 'remote_path', None))
    if args.all:
        config = utils.parse_config()
        cc_schemes = list(config['schemes'].keys())
        if args.random_order:
            random.shuffle(cc_schemes)
    elif args.schemes is not None:
        cc_schemes = args.schemes.split()
        if args.random_order:
            random.shuffle(cc_schemes)
    else:
        assert args.test_config is not None
        cc_schemes = [flow['scheme'] for flow in args.test_config['flows']]
        if args.random_order:
            random.shuffle(args.test_config['flows'])

    meta = vars(args).copy()
    meta['cc_schemes'] = sorted(cc_schemes)
    meta['git_summary'] = git_summary
    metadata_path = path.join(args.data_dir, 'pantheon_metadata.json')
    utils.save_test_metadata(meta, metadata_path)

    for run_id in range(args.start_run_id, args.start_run_id + args.run_times):
        if not hasattr(args, 'test_config') or args.test_config is None:
            for cc in cc_schemes:
                Test(args, run_id, cc).run()
        else:
            Test(args, run_id, None).run()


def pkill(args):
    sys.stderr.write('Cleaning up using pkill...(enabled by --pkill-cleanup)\n')
    if args.mode == 'remote':
        r = utils.parse_remote_path(args.remote_path)
        remote_pkill_src = path.join(r['base_dir'], 'tools', 'pkill.py')
        call(r['ssh_cmd'] + ['python3', remote_pkill_src, '--kill-dir', r['base_dir']])
    pkill_src = path.join(context.base_dir, 'tools', 'pkill.py')
    call(['python3', pkill_src, '--kill-dir', context.src_dir])


def main():
    args = arg_parser.parse_test()
    try:
        run_tests(args)
    except:
        sys.stderr.write(traceback.format_exc())
        if args.pkill_cleanup:
            pkill(args)
        sys.exit('Error in tests!')
    else:
        sys.stderr.write('All tests done!\n')


if __name__ == '__main__':
    main()

