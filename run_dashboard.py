import sys
import os

# Add project root to path
sys.path.insert(0, "/home/ec2-user/shopifly")

# Now run the actual dashboard
exec(open("dashboard/app.py").read())
