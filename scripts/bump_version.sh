#!/bin/bash
for file in "pyproject.toml" "src/moshi/__init__.py"
do
  echo -e "\tbumping: $file"
  awk '/"[0-9]+\.[0-9]+\.[0-9]+"/ { split($3, arr, "."); arr[3]++; $3 = arr[1] "." arr[2] "." arr[3] "\""; } { print }' \
    "$file" > temp && mv temp "$file"
done
