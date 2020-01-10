#!/bin/ash

# Create /Config.txt based on the environment variables we were passed

cat << EOF > /Config.txt
[Radarr]
url = $RADARR_URL
key = $RADARR_KEY
[Append]
EOF

for var in "${!APPEND_@}"; do
    printf '%s=%s\n' "$var" "${!var}" >> /Config.txt
done

# Now execute the sync script in a loop, waiting DELAY before running again
while true
do
	python /CustomFormatSync.py
	sleep $DELAY
done