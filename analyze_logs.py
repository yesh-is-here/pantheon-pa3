import os
import re
import pandas as pd

results_dir = 'results'
schemes = ['cubic', 'bbr', 'copa']

def parse_log(scheme):
    uplink_path = os.path.join(results_dir, f'{scheme}_mm_datalink_run1.log')

    timestamps_sent = []
    timestamps_ack = []
    loss_total = 0

    with open(uplink_path, 'r') as f:
        for line in f:
            match = re.match(r'^(\d+)\s+([+-])\s+\d+', line)
            if match:
                timestamp, symbol = int(match.group(1)), match.group(2)
                if symbol == '+':
                    timestamps_sent.append(timestamp)
                elif symbol == '-':
                    timestamps_ack.append(timestamp)

    if not timestamps_sent or not timestamps_ack:
        return None, None, None

    throughput_mbps = (len(timestamps_sent) * 1500 * 8) / (1_000_000 * 60)

    # RTT estimation: avg time between send and ack
    rtts = []
    for send, ack in zip(timestamps_sent, timestamps_ack):
        rtts.append(ack - send)
    avg_rtt = sum(rtts) / len(rtts) if rtts else None

    loss_rate = 100 * (1 - len(timestamps_ack) / len(timestamps_sent))

    return throughput_mbps, avg_rtt, loss_rate


data = []
for scheme in schemes:
    result = parse_log(scheme)
    if result:
        throughput, rtt, loss = result
    else:
        throughput, rtt, loss = None, None, None
    data.append([scheme.upper(), throughput, rtt, loss])

df = pd.DataFrame(data, columns=[
    'Scheme', 'Uplink Throughput (Mbps)', 'Avg RTT (ms)', 'Loss Rate (%)'
])

print(df)
df.to_csv('throughput_data.csv', index=False)

