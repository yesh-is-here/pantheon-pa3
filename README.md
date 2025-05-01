📘 Overview
This repository contains the setup, execution, analysis, and final report for Pantheon Programming Assignment 3, which evaluates the performance of three congestion control algorithms: CUBIC, BBR, and COPA using the Pantheon framework and Mahimahi emulated network environment.
🚀 Objectives
- Install and run the Pantheon testbed.
- Compare throughput, RTT, and packet loss rate across CUBIC, BBR, and COPA.
- Analyze and graphically represent the results.
- Address testbed compatibility issues (Python 3.12).
- Reflect on strengths/weaknesses of each algorithm.
⚙️ Installation & Setup
Run the following to set up:
sudo apt update
sudo apt install python3.12-venv python3.12-dev git
python3.12 -m venv venv
source venv/bin/activate
pip install pandas matplotlib
Clone the repo:
git clone https://github.com/yesh-is-here/pantheon-pa3.git
cd pantheon-pa3
Ensure pantheon and mahimahi tools are installed. If using Python 3.12, minor compatibility updates have been made to subprocess handling and decoding logic.
🧪 Running the Experiments
source venv/bin/activate
PYTHONPATH=src:src/helpers python3 src/experiments/test.py local \
  --schemes "cubic bbr copa" \
  --uplink-trace tests/12mbps_data.trace \
  --downlink-trace tests/12mbps_ack.trace \
  --data-dir results \
  --runtime 60
📊 Analysis
Run the custom analysis script to generate metrics and graphs:
python3 analyze_logs.py
This will output throughput, average RTT, and loss rate for all three algorithms. Resulting graphs are stored and used in the final report.
📎 Files Included
- analyze_logs.py: Custom analysis script.
- results/: All experiment log files and metadata.
- report.pdf: Final report with graphs and written analysis.
- Graph-Based Analysis report.pdf: Supplemental graph-centric insights.
- README.md: This file.
🤝 Collaborations & Discussion
This project was completed independently. No collaboration or external discussion (human) was involved apart from consulting online documentation and class-provided materials.
🤖 Use of LLM
An LLM assistant (ChatGPT) was used only to guide code debugging, graph formatting, and writing structure. All technical execution, experiments, and result interpretation were performed manually by the author.
