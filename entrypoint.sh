#!/bin/ash

# Create /Config.txt based on the environment variables we were passed

cat << EOF > /Config.txt
[Radarr]
url = $RADARR_URL
key = $RADARR_KEY
EOF

# Now execute the sync script in a loop, waiting DELAY before running again
while true
do
	python /CustomFormatSync.py
	sleep $DELAY
done