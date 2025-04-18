import argparse
import sys

def parse_wrapper_args(run_first):
    if run_first not in ['receiver', 'sender']:
        sys.exit('Specify "receiver" or "sender" to run first')

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='option')

    # 'deps' command
    deps_parser = subparsers.add_parser('deps', help='Print a space-separated list of build dependencies')
    deps_parser.add_argument('extra_args', nargs='*', help='Extra arguments if any')

    # 'run_first' command
    subparsers.add_parser('run_first', help='Print which side (sender or receiver) runs first')

    # 'setup' and 'setup_after_reboot'
    subparsers.add_parser('setup', help='Setup the scheme for the first time (persistent changes)')
    subparsers.add_parser('setup_after_reboot', help='Setup after reboot')

    # receiver and sender subcommands
    receiver_parser = subparsers.add_parser('receiver', help='Run receiver')
    sender_parser = subparsers.add_parser('sender', help='Run sender')

    if run_first == 'receiver':
        receiver_parser.add_argument('port', help='Port to listen on')
        sender_parser.add_argument('ip', metavar='IP', help='Receiver IP address')
        sender_parser.add_argument('port', help='Receiver port')
    else:
        sender_parser.add_argument('port', help='Port to listen on')
        receiver_parser.add_argument('ip', metavar='IP', help='Sender IP address')
        receiver_parser.add_argument('port', help='Sender port')

    args = parser.parse_args()

    if args.option == 'run_first':
        print(run_first)

    return args

def receiver_first():
    return parse_wrapper_args('receiver')

def sender_first():
    return parse_wrapper_args('sender')

