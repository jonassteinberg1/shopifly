#!/bin/bash
cd /home/ec2-user/shopifly
export PYTHONPATH="/home/ec2-user/shopifly:$PYTHONPATH"
exec streamlit run dashboard/app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true
